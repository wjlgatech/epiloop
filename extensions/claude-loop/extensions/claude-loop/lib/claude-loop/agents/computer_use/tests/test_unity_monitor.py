#!/usr/bin/env python3
"""
test_unity_monitor.py - Tests for Unity Editor log monitoring

This module provides comprehensive tests for the unity_monitor module,
including mock log data for various build scenarios.

Usage:
    # Run all tests with pytest
    pytest agents/computer_use/tests/test_unity_monitor.py -v

    # Run with coverage
    pytest agents/computer_use/tests/test_unity_monitor.py --cov=agents.computer_use.unity_monitor

    # Run without pytest
    python agents/computer_use/tests/test_unity_monitor.py
"""

import os
import tempfile
from typing import List

# Try to import pytest
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    class _MockPytest:
        """Mock pytest for running without pytest installed."""

        class fixture:
            def __init__(self, *_args, **_kwargs):
                pass

            def __call__(self, func):
                return func

        class mark:
            @staticmethod
            def parametrize(*_args, **_kwargs):
                def decorator(func):
                    return func
                return decorator

        @staticmethod
        def main(_args):
            """Mock main that returns 1 (tests not run)."""
            return 1

    pytest = _MockPytest()  # type: ignore

# Import the module we're testing
from agents.computer_use.unity_monitor import (
    UnityLogMonitor,
    BuildEventType,
    BuildPhase,
    BuildErrorInfo,
    get_unity_log_path,
)


class MockLogData:
    """Sample Unity log data for testing various scenarios."""

    @staticmethod
    def successful_build() -> str:
        """Log data for a successful Android build."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] - Starting script compilation
[12:34:58] Compiling scripts for Android
[12:35:00] - Finished script compilation
[12:35:01] Building Player
[12:35:02] [10%] Preparing build
[12:35:03] [25%] Processing assets
[12:35:05] [50%] Building scenes
[12:35:08] [75%] Packaging player
[12:35:10] [90%] Post-processing
[12:35:12] Build to: /Users/test/Project/Build/game.apk
[12:35:12] Build completed successfully
"""

    @staticmethod
    def failed_compilation() -> str:
        """Log data for a build that fails due to compilation errors."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] - Starting script compilation
Assets/Scripts/GameManager.cs(42,15): error CS0103: The name 'unknownVariable' does not exist in the current context
Assets/Scripts/PlayerController.cs(128,8): error CS1002: ; expected
[12:34:58] Build failed
"""

    @staticmethod
    def failed_asset_import() -> str:
        """Log data for a build with asset import errors."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] - Starting script compilation
[12:34:58] - Finished script compilation
[12:35:00] Failed to import texture: Assets/Textures/broken.png
[12:35:01] Asset import failed: Invalid texture format
[12:35:02] Build completed with errors
"""

    @staticmethod
    def shader_compilation_error() -> str:
        """Log data with shader compilation errors."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] Compiling shader "Custom/MyShader"
[12:34:58] Shader error in 'Custom/MyShader': undeclared identifier 'foo' at line 15
[12:34:59] Failed to compile shader: Custom/MyShader
[12:35:00] Build failed
"""

    @staticmethod
    def cancelled_build() -> str:
        """Log data for a cancelled build."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] - Starting script compilation
[12:34:58] [25%] Processing assets
[12:35:00] User cancelled
"""

    @staticmethod
    def build_with_warnings() -> str:
        """Log data for a successful build with warnings."""
        return """[12:34:56] Starting build for platform Android
[12:34:56] *** Build started
[12:34:57] - Starting script compilation
Assets/Scripts/OldCode.cs(10,5): warning CS0618: 'Method' is obsolete
Assets/Scripts/Utils.cs(25,10): warning CS0414: The field is never used
[12:34:58] - Finished script compilation
[12:35:00] Build completed successfully
"""


class TestBuildErrorInfo:
    """Tests for the BuildErrorInfo dataclass."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = BuildErrorInfo(
            error_type="compilation",
            message="Variable not found"
        )
        assert error.error_type == "compilation"
        assert error.message == "Variable not found"
        assert error.file_path is None
        assert error.line_number is None

    def test_error_with_location(self):
        """Test error with file location."""
        error = BuildErrorInfo(
            error_type="compilation",
            message="Syntax error",
            file_path="Assets/Scripts/Test.cs",
            line_number=42,
            column_number=15
        )
        assert "Assets/Scripts/Test.cs:42:15" in str(error)
        assert "Syntax error" in str(error)

    def test_error_str_without_location(self):
        """Test string representation without location."""
        error = BuildErrorInfo(
            error_type="asset",
            message="Failed to import texture"
        )
        assert "[asset]" in str(error).lower()
        assert "Failed to import texture" in str(error)


class TestUnityLogMonitor:
    """Tests for the UnityLogMonitor class."""

    def test_default_log_path(self):
        """Test default log path is set correctly."""
        monitor = UnityLogMonitor()
        expected_path = os.path.expanduser("~/Library/Logs/Unity/Editor.log")
        assert str(monitor.log_path) == expected_path

    def test_custom_log_path(self):
        """Test custom log path is used."""
        custom_path = "/tmp/custom_unity.log"
        monitor = UnityLogMonitor(log_path=custom_path)
        assert str(monitor.log_path) == custom_path

    def test_log_exists_false(self):
        """Test log_exists returns False for missing file."""
        monitor = UnityLogMonitor(log_path="/nonexistent/path/Editor.log")
        assert not monitor.log_exists()

    def test_log_exists_true(self):
        """Test log_exists returns True for existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write("test log content\n")
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path)
            assert monitor.log_exists()
        finally:
            os.unlink(temp_path)

    def test_clear_state(self):
        """Test clear_state resets internal state."""
        monitor = UnityLogMonitor()
        monitor._errors = [BuildErrorInfo(error_type="test", message="test")]
        monitor._warnings = ["warning"]
        monitor._current_phase = BuildPhase.BUILDING_PLAYER
        monitor._output_path = "/some/path"

        monitor.clear_state()

        assert monitor._errors == []
        assert monitor._warnings == []
        assert monitor._current_phase == BuildPhase.IDLE
        assert monitor._output_path is None


class TestLogParsing:
    """Tests for log line parsing functionality."""

    def test_detect_build_start(self):
        """Test detection of build start messages."""
        monitor = UnityLogMonitor()

        test_cases = [
            "*** Build started",
            "Building Player",
            "Starting build for Android",
            "[12:34:56] Build started",
        ]

        for line in test_cases:
            monitor.clear_state()
            event = monitor._process_line(line)
            assert event is not None, f"Failed to detect: {line}"
            assert event.event_type == BuildEventType.BUILD_STARTED

    def test_detect_build_success(self):
        """Test detection of build success messages."""
        monitor = UnityLogMonitor()

        test_cases = [
            "Build completed successfully",
            "Build succeeded",
            "*** Build completed",
            "Successfully built player to /path/to/build",
        ]

        for line in test_cases:
            monitor.clear_state()
            event = monitor._process_line(line)
            assert event is not None, f"Failed to detect: {line}"
            assert event.event_type == BuildEventType.BUILD_SUCCESS

    def test_detect_build_failure(self):
        """Test detection of build failure messages."""
        monitor = UnityLogMonitor()

        test_cases = [
            "Build failed",
            "Build completed with errors",
            "Error building Player",
            "BUILD FAILED",
        ]

        for line in test_cases:
            monitor.clear_state()
            event = monitor._process_line(line)
            assert event is not None, f"Failed to detect: {line}"
            assert event.event_type == BuildEventType.BUILD_FAILED

    def test_detect_build_cancelled(self):
        """Test detection of cancelled build messages."""
        monitor = UnityLogMonitor()

        test_cases = [
            "Build cancelled",
            "Build aborted",
            "User cancelled",
        ]

        for line in test_cases:
            monitor.clear_state()
            event = monitor._process_line(line)
            assert event is not None, f"Failed to detect: {line}"
            assert event.event_type == BuildEventType.BUILD_CANCELLED

    def test_detect_progress(self):
        """Test detection of progress indicators."""
        monitor = UnityLogMonitor()

        test_cases = [
            ("[50%] Building scenes", 50.0),
            ("Progress: 75%", 75.0),
            ("Building: 33.5%", 33.5),
        ]

        for line, expected_progress in test_cases:
            monitor.clear_state()
            event = monitor._process_line(line)
            assert event is not None, f"Failed to detect: {line}"
            assert event.event_type == BuildEventType.BUILD_PROGRESS
            assert event.progress_percent == expected_progress

    def test_parse_compilation_error(self):
        """Test parsing of compilation errors with file location."""
        monitor = UnityLogMonitor()

        line = "Assets/Scripts/GameManager.cs(42,15): error CS0103: The name 'unknownVariable' does not exist"
        event = monitor._process_line(line)

        assert event is not None
        assert event.event_type == BuildEventType.SCRIPT_ERROR
        assert len(monitor._errors) == 1

        error = monitor._errors[0]
        assert error.error_type == "compilation"
        assert error.file_path == "Assets/Scripts/GameManager.cs"
        assert error.line_number == 42
        assert error.column_number == 15
        assert error.error_code == "CS0103"

    def test_parse_asset_error(self):
        """Test parsing of asset import errors."""
        monitor = UnityLogMonitor()

        line = "Failed to import texture: Assets/Textures/broken.png"
        event = monitor._process_line(line)

        assert event is not None
        assert event.event_type == BuildEventType.ASSET_ERROR
        assert len(monitor._errors) == 1
        assert monitor._errors[0].error_type == "asset"

    def test_ignore_empty_lines(self):
        """Test that empty lines are ignored."""
        monitor = UnityLogMonitor()

        event = monitor._process_line("")
        assert event is None

        event = monitor._process_line("   \t  ")
        assert event is None

    def test_track_warnings(self):
        """Test that warnings are tracked."""
        monitor = UnityLogMonitor()

        warning_line = "Assets/Scripts/Test.cs(10,5): warning CS0618: Method is obsolete"
        monitor._process_line(warning_line)

        assert len(monitor._warnings) == 1


class TestBuildMonitoring:
    """Tests for full build monitoring functionality."""

    def test_successful_build_monitoring(self):
        """Test monitoring a complete successful build."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(MockLogData.successful_build())
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path, poll_interval=0.01)
            result = monitor.wait_for_build_completion(
                timeout_seconds=5.0,
                from_current_position=False
            )

            assert result.success
            assert result.status == BuildPhase.COMPLETE
            assert len(result.errors) == 0
            assert not result.timed_out
            assert result.output_path == "/Users/test/Project/Build/game.apk"
        finally:
            os.unlink(temp_path)

    def test_failed_compilation_monitoring(self):
        """Test monitoring a build that fails compilation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(MockLogData.failed_compilation())
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path, poll_interval=0.01)
            result = monitor.wait_for_build_completion(
                timeout_seconds=5.0,
                from_current_position=False
            )

            assert not result.success
            assert result.status == BuildPhase.FAILED
            assert len(result.errors) == 2
            assert any("GameManager.cs" in str(e) for e in result.errors)
            assert any("PlayerController.cs" in str(e) for e in result.errors)
        finally:
            os.unlink(temp_path)

    def test_cancelled_build_monitoring(self):
        """Test monitoring a cancelled build."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(MockLogData.cancelled_build())
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path, poll_interval=0.01)
            result = monitor.wait_for_build_completion(
                timeout_seconds=5.0,
                from_current_position=False
            )

            assert not result.success
            assert result.status == BuildPhase.FAILED
        finally:
            os.unlink(temp_path)

    def test_timeout_handling(self):
        """Test that timeout is handled correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            # Write only the start of a build, no completion
            f.write("[12:34:56] *** Build started\n")
            f.write("[12:34:57] - Starting script compilation\n")
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path, poll_interval=0.01)
            result = monitor.wait_for_build_completion(
                timeout_seconds=0.5,  # Short timeout
                from_current_position=False
            )

            assert not result.success
            assert result.timed_out
        finally:
            os.unlink(temp_path)

    def test_missing_log_file(self):
        """Test handling of missing log file."""
        monitor = UnityLogMonitor(log_path="/nonexistent/Editor.log")
        result = monitor.wait_for_build_completion(timeout_seconds=1.0)

        assert not result.success
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message.lower()

    def test_progress_callback(self):
        """Test that progress callback is called."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(MockLogData.successful_build())
            temp_path = f.name

        try:
            progress_updates: List[tuple] = []

            def callback(percent: float, message: str, phase: BuildPhase) -> None:
                progress_updates.append((percent, message, phase))

            monitor = UnityLogMonitor(log_path=temp_path, poll_interval=0.01)
            monitor.set_progress_callback(callback)
            result = monitor.wait_for_build_completion(
                timeout_seconds=5.0,
                from_current_position=False
            )

            assert result.success
            assert len(progress_updates) > 0
            # Should have progress at various points
            percentages = [p[0] for p in progress_updates]
            assert 0.0 in percentages or 10.0 in percentages  # Build start or compilation start
            assert 100.0 in percentages  # Build complete
        finally:
            os.unlink(temp_path)


class TestGetRecentErrors:
    """Tests for the get_recent_errors method."""

    def test_get_recent_errors(self):
        """Test getting recent errors from log."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(MockLogData.failed_compilation())
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path)
            errors = monitor.get_recent_errors(max_lines=100)

            assert len(errors) == 2
            assert any(e.file_path == "Assets/Scripts/GameManager.cs" for e in errors)
        finally:
            os.unlink(temp_path)

    def test_get_recent_errors_empty_log(self):
        """Test getting errors from empty log."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write("")
            temp_path = f.name

        try:
            monitor = UnityLogMonitor(log_path=temp_path)
            errors = monitor.get_recent_errors()
            assert errors == []
        finally:
            os.unlink(temp_path)

    def test_get_recent_errors_nonexistent_file(self):
        """Test getting errors from nonexistent file."""
        monitor = UnityLogMonitor(log_path="/nonexistent/Editor.log")
        errors = monitor.get_recent_errors()
        assert errors == []


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_unity_log_path(self):
        """Test get_unity_log_path returns expected path."""
        path = get_unity_log_path()
        assert "Library/Logs/Unity/Editor.log" in path


class TestBuildPhaseTransitions:
    """Tests for build phase state transitions."""

    def test_phase_progression(self):
        """Test that phases progress correctly through a build."""
        monitor = UnityLogMonitor()

        # Start build
        monitor._process_line("*** Build started")
        assert monitor._current_phase == BuildPhase.PREPARING

        # Compilation start
        monitor._process_line("- Starting script compilation")
        assert monitor._current_phase == BuildPhase.COMPILING_SCRIPTS

        # Success
        monitor._process_line("Build completed successfully")
        assert monitor._current_phase == BuildPhase.COMPLETE

    def test_phase_failure(self):
        """Test that failure sets phase correctly."""
        monitor = UnityLogMonitor()

        monitor._process_line("*** Build started")
        monitor._process_line("Build failed")
        assert monitor._current_phase == BuildPhase.FAILED


# Run tests without pytest
def run_tests_without_pytest():
    """Run tests without pytest framework."""
    import traceback

    test_classes = [
        TestBuildErrorInfo,
        TestUnityLogMonitor,
        TestLogParsing,
        TestBuildMonitoring,
        TestGetRecentErrors,
        TestConvenienceFunctions,
        TestBuildPhaseTransitions,
    ]

    total = 0
    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total += 1
                try:
                    getattr(instance, method_name)()
                    passed += 1
                    print(f"  ✓ {test_class.__name__}.{method_name}")
                except Exception as e:
                    failed += 1
                    print(f"  ✗ {test_class.__name__}.{method_name}: {e}")
                    traceback.print_exc()

    print(f"\n{passed}/{total} tests passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    if PYTEST_AVAILABLE:
        import sys
        sys.exit(pytest.main([__file__, '-v']))
    else:
        print("Running tests without pytest...")
        success = run_tests_without_pytest()
        import sys
        sys.exit(0 if success else 1)
