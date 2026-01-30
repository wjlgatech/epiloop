#!/usr/bin/env python3
"""
unity_monitor.py - Unity Editor log monitoring for macOS

This module provides real-time monitoring of Unity's Editor.log file to track
build progress, detect errors, and report completion status.

Usage:
    from agents.computer_use.unity_monitor import UnityLogMonitor

    monitor = UnityLogMonitor()
    result = monitor.wait_for_build_completion(timeout_seconds=300)
    print(f"Build completed: {result.status}")
"""

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Iterator


class BuildEventType(Enum):
    """Types of build events detected in Unity logs."""
    BUILD_STARTED = "build_started"
    BUILD_PROGRESS = "build_progress"
    BUILD_SUCCESS = "build_success"
    BUILD_FAILED = "build_failed"
    BUILD_CANCELLED = "build_cancelled"
    COMPILATION_STARTED = "compilation_started"
    COMPILATION_FINISHED = "compilation_finished"
    SCRIPT_ERROR = "script_error"
    ASSET_IMPORT = "asset_import"
    ASSET_ERROR = "asset_error"
    SHADER_COMPILE = "shader_compile"
    UNKNOWN = "unknown"


class BuildPhase(Enum):
    """Current phase of the build process."""
    IDLE = "idle"
    PREPARING = "preparing"
    COMPILING_SCRIPTS = "compiling_scripts"
    IMPORTING_ASSETS = "importing_assets"
    BUILDING_PLAYER = "building_player"
    PACKAGING = "packaging"
    POST_PROCESSING = "post_processing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class BuildEvent:
    """A detected build event from the Unity log."""
    event_type: BuildEventType
    timestamp: datetime
    message: str
    phase: BuildPhase = BuildPhase.IDLE
    progress_percent: Optional[float] = None
    details: Optional[str] = None
    raw_line: Optional[str] = None


@dataclass
class BuildErrorInfo:
    """Structured information about a build error."""
    error_type: str  # "compilation", "asset", "manifest", "signing", "shader", etc.
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __str__(self) -> str:
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"
                if self.column_number:
                    location += f":{self.column_number}"
        return f"[{self.error_type}] {self.message}{location}"


@dataclass
class BuildMonitorResult:
    """Result from monitoring a build operation."""
    status: BuildPhase
    success: bool
    errors: List[BuildErrorInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    events: List[BuildEvent] = field(default_factory=list)
    duration_seconds: float = 0.0
    output_path: Optional[str] = None
    timed_out: bool = False


# Progress callback type: receives (progress_percent, message, phase)
ProgressCallback = Callable[[float, str, BuildPhase], None]


class UnityLogMonitor:
    """
    Monitors Unity's Editor.log for build progress and completion.

    This class provides:
    - Tail-like following of the Unity Editor.log file
    - Detection of build start, progress, success, and failure
    - Parsing of compilation and asset errors
    - Timeout support with configurable duration
    - Progress event callbacks

    Default log location: ~/Library/Logs/Unity/Editor.log
    """

    # Regex patterns for detecting build events
    PATTERNS = {
        # Build start indicators
        'build_start': [
            re.compile(r'^\[.*?\]\s*Build started', re.IGNORECASE),
            re.compile(r'^Building Player', re.IGNORECASE),
            re.compile(r'^Starting build', re.IGNORECASE),
            re.compile(r'^\*\*\* Build started', re.IGNORECASE),
        ],

        # Build success indicators
        'build_success': [
            re.compile(r'Build completed successfully', re.IGNORECASE),
            re.compile(r'Build succeeded', re.IGNORECASE),
            re.compile(r'^\*\*\* Build completed', re.IGNORECASE),
            re.compile(r'^Build finished', re.IGNORECASE),
            re.compile(r'Successfully built player', re.IGNORECASE),
        ],

        # Build failure indicators
        'build_failed': [
            re.compile(r'Build failed', re.IGNORECASE),
            re.compile(r'Build completed with errors', re.IGNORECASE),
            re.compile(r'^Error building Player', re.IGNORECASE),
            re.compile(r'^\*\*\* Build failed', re.IGNORECASE),
            re.compile(r'BUILD FAILED', re.IGNORECASE),
        ],

        # Build cancelled
        'build_cancelled': [
            re.compile(r'Build cancelled', re.IGNORECASE),
            re.compile(r'Build aborted', re.IGNORECASE),
            re.compile(r'User cancelled', re.IGNORECASE),
        ],

        # Compilation events
        'compilation_start': [
            re.compile(r'^- Starting script compilation', re.IGNORECASE),
            re.compile(r'^Compiling scripts', re.IGNORECASE),
            re.compile(r'^\*\*\* Script compilation started'),
        ],
        'compilation_end': [
            re.compile(r'^- Finished script compilation', re.IGNORECASE),
            re.compile(r'^Script compilation finished', re.IGNORECASE),
        ],

        # Script/compilation errors
        'script_error': [
            re.compile(
                r'^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s*error\s*(?P<code>\w+)?:\s*(?P<msg>.+)$',
                re.IGNORECASE
            ),
            re.compile(r'^error CS\d+:', re.IGNORECASE),
            re.compile(r'^Assets/.*?:\s*error', re.IGNORECASE),
        ],

        # Asset errors
        'asset_error': [
            re.compile(r'^Failed to import', re.IGNORECASE),
            re.compile(r'^Asset import failed', re.IGNORECASE),
            re.compile(r'^Error importing asset', re.IGNORECASE),
        ],

        # Shader compilation
        'shader_compile': [
            re.compile(r'^Compiling shader', re.IGNORECASE),
            re.compile(r'^Shader compilation', re.IGNORECASE),
        ],
        'shader_error': [
            re.compile(r'^Shader error', re.IGNORECASE),
            re.compile(r'^Failed to compile shader', re.IGNORECASE),
        ],

        # Progress indicators
        'progress': [
            re.compile(r'\[(?P<percent>\d+(?:\.\d+)?)\s*%\]'),
            re.compile(r'^Building:?\s*(?P<percent>\d+(?:\.\d+)?)\s*%'),
            re.compile(r'^Progress:\s*(?P<percent>\d+(?:\.\d+)?)\s*%'),
        ],

        # Asset import progress
        'asset_import': [
            re.compile(r'^Importing\s+(?P<asset>.+)'),
            re.compile(r'^Import Asset:\s*(?P<asset>.+)'),
        ],

        # Build output path
        'output_path': [
            re.compile(r'Build to:\s*(?P<path>.+)$'),
            re.compile(r'Building player to:\s*(?P<path>.+)$'),
            re.compile(r'Output:\s*(?P<path>.+)$'),
        ],
    }

    def __init__(
        self,
        log_path: Optional[str] = None,
        poll_interval: float = 0.5
    ):
        """
        Initialize the Unity log monitor.

        Args:
            log_path: Path to the Unity Editor.log file.
                     Default: ~/Library/Logs/Unity/Editor.log
            poll_interval: How often to poll the log file for changes (seconds).
        """
        if log_path is None:
            log_path = os.path.expanduser("~/Library/Logs/Unity/Editor.log")
        self._log_path = Path(log_path)
        self._poll_interval = poll_interval
        self._last_position = 0
        self._current_phase = BuildPhase.IDLE
        self._errors: List[BuildErrorInfo] = []
        self._warnings: List[str] = []
        self._events: List[BuildEvent] = []
        self._progress_callback: Optional[ProgressCallback] = None
        self._output_path: Optional[str] = None

    @property
    def log_path(self) -> Path:
        """Get the path to the Unity log file."""
        return self._log_path

    def log_exists(self) -> bool:
        """Check if the Unity log file exists."""
        return self._log_path.exists()

    def set_progress_callback(self, callback: Optional[ProgressCallback]) -> None:
        """Set a callback function for progress updates."""
        self._progress_callback = callback

    def _emit_progress(self, percent: float, message: str, phase: BuildPhase) -> None:
        """Emit a progress event to the callback if set."""
        if self._progress_callback:
            try:
                self._progress_callback(percent, message, phase)
            except Exception:
                pass  # Don't let callback errors stop monitoring

    def _create_event(
        self,
        event_type: BuildEventType,
        message: str,
        raw_line: str,
        progress: Optional[float] = None,
        details: Optional[str] = None
    ) -> BuildEvent:
        """Create a build event and add it to the events list."""
        event = BuildEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            message=message,
            phase=self._current_phase,
            progress_percent=progress,
            details=details,
            raw_line=raw_line
        )
        self._events.append(event)
        return event

    def _parse_error_from_line(self, line: str) -> Optional[BuildErrorInfo]:
        """Parse an error from a log line."""
        # Try to match structured error format: file(line,col): error CODE: message
        for pattern in self.PATTERNS['script_error']:
            match = pattern.search(line)
            if match:
                groups = match.groupdict()
                return BuildErrorInfo(
                    error_type="compilation",
                    message=groups.get('msg', line),
                    file_path=groups.get('file'),
                    line_number=int(groups['line']) if groups.get('line') else None,
                    column_number=int(groups['col']) if groups.get('col') else None,
                    error_code=groups.get('code'),
                    timestamp=datetime.now()
                )

        # Check for asset errors
        for pattern in self.PATTERNS['asset_error']:
            if pattern.search(line):
                return BuildErrorInfo(
                    error_type="asset",
                    message=line.strip(),
                    timestamp=datetime.now()
                )

        # Check for shader errors
        for pattern in self.PATTERNS['shader_error']:
            if pattern.search(line):
                return BuildErrorInfo(
                    error_type="shader",
                    message=line.strip(),
                    timestamp=datetime.now()
                )

        return None

    def _process_line(self, line: str) -> Optional[BuildEvent]:
        """Process a single log line and return any detected event."""
        line = line.rstrip('\n\r')
        if not line.strip():
            return None

        # Check for build start
        for pattern in self.PATTERNS['build_start']:
            if pattern.search(line):
                self._current_phase = BuildPhase.PREPARING
                event = self._create_event(
                    BuildEventType.BUILD_STARTED,
                    "Build started",
                    line
                )
                self._emit_progress(0.0, "Build started", self._current_phase)
                return event

        # Check for build success
        for pattern in self.PATTERNS['build_success']:
            if pattern.search(line):
                self._current_phase = BuildPhase.COMPLETE
                event = self._create_event(
                    BuildEventType.BUILD_SUCCESS,
                    "Build succeeded",
                    line,
                    progress=100.0
                )
                self._emit_progress(100.0, "Build complete", self._current_phase)
                return event

        # Check for build failure
        for pattern in self.PATTERNS['build_failed']:
            if pattern.search(line):
                self._current_phase = BuildPhase.FAILED
                event = self._create_event(
                    BuildEventType.BUILD_FAILED,
                    "Build failed",
                    line
                )
                self._emit_progress(0.0, "Build failed", self._current_phase)
                return event

        # Check for build cancelled
        for pattern in self.PATTERNS['build_cancelled']:
            if pattern.search(line):
                self._current_phase = BuildPhase.FAILED
                event = self._create_event(
                    BuildEventType.BUILD_CANCELLED,
                    "Build cancelled",
                    line
                )
                self._emit_progress(0.0, "Build cancelled", self._current_phase)
                return event

        # Check for compilation start
        for pattern in self.PATTERNS['compilation_start']:
            if pattern.search(line):
                self._current_phase = BuildPhase.COMPILING_SCRIPTS
                event = self._create_event(
                    BuildEventType.COMPILATION_STARTED,
                    "Script compilation started",
                    line
                )
                self._emit_progress(10.0, "Compiling scripts", self._current_phase)
                return event

        # Check for compilation end
        for pattern in self.PATTERNS['compilation_end']:
            if pattern.search(line):
                event = self._create_event(
                    BuildEventType.COMPILATION_FINISHED,
                    "Script compilation finished",
                    line
                )
                self._emit_progress(30.0, "Scripts compiled", self._current_phase)
                return event

        # Check for progress indicators
        for pattern in self.PATTERNS['progress']:
            match = pattern.search(line)
            if match:
                percent = float(match.group('percent'))
                event = self._create_event(
                    BuildEventType.BUILD_PROGRESS,
                    f"Build progress: {percent}%",
                    line,
                    progress=percent
                )
                self._emit_progress(percent, f"Building: {percent}%", self._current_phase)
                return event

        # Check for output path
        for pattern in self.PATTERNS['output_path']:
            match = pattern.search(line)
            if match:
                self._output_path = match.group('path').strip()
                return None

        # Check for errors
        error_info = self._parse_error_from_line(line)
        if error_info:
            self._errors.append(error_info)
            event = self._create_event(
                BuildEventType.SCRIPT_ERROR if error_info.error_type == "compilation"
                else BuildEventType.ASSET_ERROR,
                str(error_info),
                line,
                details=error_info.message
            )
            return event

        # Check for warnings (simple heuristic)
        lower_line = line.lower()
        if 'warning' in lower_line and (':' in line or 'warning ' in lower_line):
            self._warnings.append(line.strip())

        return None

    def tail_log(
        self,
        from_end: bool = True,
        max_initial_lines: int = 100
    ) -> Iterator[str]:
        """
        Tail the Unity log file, yielding new lines as they appear.

        Args:
            from_end: If True, start from near the end of file.
                     If False, start from beginning.
            max_initial_lines: When from_end is True, how many lines to read initially.

        Yields:
            New lines from the log file as they appear.
        """
        if not self.log_exists():
            raise FileNotFoundError(f"Unity log not found: {self._log_path}")

        with open(self._log_path, 'r', encoding='utf-8', errors='replace') as f:
            if from_end:
                # Seek to near end of file
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                if file_size > 0:
                    # Read backwards to find starting position
                    # Estimate: average line is ~100 chars
                    seek_pos = max(0, file_size - (max_initial_lines * 100))
                    f.seek(seek_pos)
                    if seek_pos > 0:
                        f.readline()  # Skip partial line
                    # Read remaining lines
                    for line in f:
                        yield line
            else:
                # Read from beginning
                for line in f:
                    yield line

            # Now follow the file
            self._last_position = f.tell()

            while True:
                line = f.readline()
                if line:
                    yield line
                    self._last_position = f.tell()
                else:
                    # Check if file was truncated/rotated
                    try:
                        current_size = os.path.getsize(self._log_path)
                        if current_size < self._last_position:
                            # File was truncated, start over
                            f.seek(0)
                            self._last_position = 0
                            continue
                    except OSError:
                        pass
                    time.sleep(self._poll_interval)

    def wait_for_build_completion(
        self,
        timeout_seconds: float = 600.0,
        from_current_position: bool = True
    ) -> BuildMonitorResult:
        """
        Wait for a build to complete, tracking progress and errors.

        Args:
            timeout_seconds: Maximum time to wait for build completion.
            from_current_position: If True, only process new log lines.

        Returns:
            BuildMonitorResult with status, errors, and timing information.
        """
        start_time = time.time()
        self._errors = []
        self._warnings = []
        self._events = []
        self._current_phase = BuildPhase.IDLE
        self._output_path = None

        if not self.log_exists():
            return BuildMonitorResult(
                status=BuildPhase.FAILED,
                success=False,
                errors=[BuildErrorInfo(
                    error_type="system",
                    message=f"Unity log file not found: {self._log_path}"
                )],
                duration_seconds=0.0
            )

        try:
            with open(self._log_path, 'r', encoding='utf-8', errors='replace') as f:
                # Position at start or near end
                if from_current_position:
                    f.seek(0, 2)  # Go to end
                    file_size = f.tell()
                    if file_size > 0:
                        seek_pos = max(0, file_size - (100 * 100))  # ~100 lines back
                        f.seek(seek_pos)
                        if seek_pos > 0:
                            f.readline()  # Skip partial line

                self._last_position = f.tell()

                # Poll loop with timeout checks
                while True:
                    # Check timeout first
                    elapsed = time.time() - start_time
                    if elapsed > timeout_seconds:
                        return BuildMonitorResult(
                            status=self._current_phase,
                            success=False,
                            errors=self._errors,
                            warnings=self._warnings,
                            events=self._events,
                            duration_seconds=elapsed,
                            output_path=self._output_path,
                            timed_out=True
                        )

                    # Try to read a line
                    line = f.readline()
                    if line:
                        self._last_position = f.tell()
                        self._process_line(line)

                        # Check for terminal states
                        if self._current_phase == BuildPhase.COMPLETE:
                            return BuildMonitorResult(
                                status=BuildPhase.COMPLETE,
                                success=True,
                                errors=self._errors,
                                warnings=self._warnings,
                                events=self._events,
                                duration_seconds=time.time() - start_time,
                                output_path=self._output_path
                            )

                        if self._current_phase == BuildPhase.FAILED:
                            return BuildMonitorResult(
                                status=BuildPhase.FAILED,
                                success=False,
                                errors=self._errors,
                                warnings=self._warnings,
                                events=self._events,
                                duration_seconds=time.time() - start_time,
                                output_path=self._output_path
                            )
                    else:
                        # No new data - check if file was truncated/rotated
                        try:
                            current_size = os.path.getsize(self._log_path)
                            if current_size < self._last_position:
                                f.seek(0)
                                self._last_position = 0
                                continue
                        except OSError:
                            pass
                        # Sleep briefly before polling again
                        time.sleep(self._poll_interval)

        except KeyboardInterrupt:
            return BuildMonitorResult(
                status=self._current_phase,
                success=False,
                errors=self._errors,
                warnings=self._warnings,
                events=self._events,
                duration_seconds=time.time() - start_time,
                output_path=self._output_path
            )

        # Should not reach here normally
        return BuildMonitorResult(
            status=self._current_phase,
            success=False,
            errors=self._errors,
            warnings=self._warnings,
            events=self._events,
            duration_seconds=time.time() - start_time,
            output_path=self._output_path
        )

    def get_recent_errors(self, max_lines: int = 1000) -> List[BuildErrorInfo]:
        """
        Scan recent log entries for errors without waiting for build.

        Args:
            max_lines: Maximum number of lines to scan from end of log.

        Returns:
            List of errors found in recent log entries.
        """
        errors: List[BuildErrorInfo] = []

        if not self.log_exists():
            return errors

        try:
            with open(self._log_path, 'r', encoding='utf-8', errors='replace') as f:
                # Read last N lines
                f.seek(0, 2)
                file_size = f.tell()
                seek_pos = max(0, file_size - (max_lines * 100))
                f.seek(seek_pos)
                if seek_pos > 0:
                    f.readline()  # Skip partial line

                for line in f:
                    error_info = self._parse_error_from_line(line)
                    if error_info:
                        errors.append(error_info)
        except Exception:
            pass

        return errors

    def clear_state(self) -> None:
        """Clear the internal monitoring state."""
        self._errors = []
        self._warnings = []
        self._events = []
        self._current_phase = BuildPhase.IDLE
        self._output_path = None
        self._last_position = 0


# Convenience functions

def get_unity_log_path() -> str:
    """Get the default Unity Editor.log path."""
    return os.path.expanduser("~/Library/Logs/Unity/Editor.log")


def monitor_unity_build(
    timeout_seconds: float = 600.0,
    progress_callback: Optional[ProgressCallback] = None
) -> BuildMonitorResult:
    """
    Monitor Unity for build completion.

    Args:
        timeout_seconds: Maximum time to wait.
        progress_callback: Optional callback for progress updates.

    Returns:
        BuildMonitorResult with build status and any errors.
    """
    monitor = UnityLogMonitor()
    if progress_callback:
        monitor.set_progress_callback(progress_callback)
    return monitor.wait_for_build_completion(timeout_seconds)


def get_recent_unity_errors(max_lines: int = 1000) -> List[BuildErrorInfo]:
    """
    Get recent errors from Unity's log.

    Args:
        max_lines: Maximum lines to scan.

    Returns:
        List of recent errors.
    """
    monitor = UnityLogMonitor()
    return monitor.get_recent_errors(max_lines)
