#!/usr/bin/env python3
"""
action_logger.py - Action Logging with Screenshots for GUI Automation

This module provides comprehensive logging of all GUI actions for debugging
automation workflows. Each action is logged with:
- Timestamp
- Action type (click, type, wait, etc.)
- Target element/description
- Result (success/failure)
- Before/after screenshots

Features:
- Persistent session logs stored in .claude-loop/screenshots/{timestamp}/
- HTML report generation with screenshot timeline
- Log rotation (keep last N sessions)
- Support for --no-screenshots flag to disable capture
- Export functionality for sharing/debugging

Usage:
    from agents.computer_use.action_logger import ActionLogger

    logger = ActionLogger()
    logger.start_session("Unity Build Workflow")

    # Log an action with screenshots
    action_id = logger.log_action(
        action_type="click",
        target="Build button",
        details={"app": "Unity", "method": "applescript"},
        capture_before=True
    )

    # Mark action complete
    logger.complete_action(action_id, success=True, capture_after=True)

    # Generate report and end session
    logger.end_session()
    logger.generate_report()
"""

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from html import escape

# Set up logging
logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of GUI actions that can be logged."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEY_PRESS = "key_press"
    WAIT = "wait"
    WAIT_FOR_ELEMENT = "wait_for_element"
    SCREENSHOT = "screenshot"
    DRAG = "drag"
    SCROLL = "scroll"
    MENU_SELECT = "menu_select"
    DIALOG_HANDLE = "dialog_handle"
    PANEL_DETECT = "panel_detect"
    VISION_DETECT = "vision_detect"
    CUSTOM = "custom"


class ActionStatus(Enum):
    """Status of a logged action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class ActionLogEntry:
    """
    Represents a single logged action.

    Contains all information about an action including:
    - When it occurred
    - What was attempted
    - What the result was
    - Screenshots before/after
    """
    action_id: str
    action_type: str
    target: str
    status: str = ActionStatus.PENDING.value
    timestamp_start: str = ""
    timestamp_end: Optional[str] = None
    duration_ms: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    result_details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    # Screenshot paths relative to session directory
    before_screenshot: Optional[str] = None
    after_screenshot: Optional[str] = None

    # Coordinates (if applicable)
    x: Optional[float] = None
    y: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "status": self.status,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "result_details": self.result_details,
            "error_message": self.error_message,
            "before_screenshot": self.before_screenshot,
            "after_screenshot": self.after_screenshot,
            "x": self.x,
            "y": self.y,
        }


@dataclass
class SessionInfo:
    """Information about a logging session."""
    session_id: str
    name: str
    started_at: str
    ended_at: Optional[str] = None
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    session_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "session_dir": self.session_dir,
        }


# Default base directory for screenshot sessions
DEFAULT_SCREENSHOTS_BASE = Path(".claude-loop/screenshots")

# Screenshot capture availability
SCREENSHOT_CAPTURE_AVAILABLE = False
try:
    from .screenshot import MultiMonitorCapture
    SCREENSHOT_CAPTURE_AVAILABLE = True
except ImportError:
    MultiMonitorCapture = None  # type: ignore


class ActionLogger:
    """
    Logger for GUI automation actions with screenshot capture.

    This class provides:
    - Session-based logging with timestamps
    - Before/after screenshot capture for each action
    - JSON metadata files for programmatic access
    - HTML report generation with visual timeline
    - Log rotation to manage disk space
    - Export functionality for sharing

    Example:
        logger = ActionLogger()
        logger.start_session("My Workflow")

        # Log a click action
        action_id = logger.log_action(
            action_type=ActionType.CLICK,
            target="Submit button",
            capture_before=True
        )

        # ... perform the click ...

        logger.complete_action(action_id, success=True, capture_after=True)
        logger.end_session()
        logger.generate_report()
    """

    # Default configuration
    DEFAULT_MAX_SESSIONS = 10
    DEFAULT_SCREENSHOT_FORMAT = "png"

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        enable_screenshots: bool = True,
        screenshot_format: str = DEFAULT_SCREENSHOT_FORMAT,
    ):
        """
        Initialize the ActionLogger.

        Args:
            base_dir: Base directory for storing sessions.
                     Defaults to .claude-loop/screenshots/
            max_sessions: Maximum number of sessions to keep before rotation.
            enable_screenshots: If False, skip screenshot capture.
            screenshot_format: Image format for screenshots (png, jpg).
        """
        self._base_dir = Path(base_dir) if base_dir else DEFAULT_SCREENSHOTS_BASE
        self._max_sessions = max_sessions
        self._enable_screenshots = enable_screenshots
        self._screenshot_format = screenshot_format

        # Current session state
        self._session: Optional[SessionInfo] = None
        self._session_dir: Optional[Path] = None
        self._actions: List[ActionLogEntry] = []
        self._action_counter = 0

        # Screenshot capture
        self._capture: Optional[Any] = None
        if SCREENSHOT_CAPTURE_AVAILABLE and self._enable_screenshots and MultiMonitorCapture is not None:
            try:
                self._capture = MultiMonitorCapture()
            except Exception as e:
                logger.warning(f"Failed to initialize screenshot capture: {e}")

    def start_session(self, name: str = "Session") -> str:
        """
        Start a new logging session.

        Creates a new session directory and initializes logging state.
        Performs log rotation if necessary.

        Args:
            name: Human-readable name for the session.

        Returns:
            Session ID (timestamp-based).
        """
        # End any existing session
        if self._session is not None:
            self.end_session()

        # Perform log rotation before starting new session
        self._rotate_sessions()

        # Create session
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S")
        session_dir = self._base_dir / session_id

        # Create session directory structure
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "screenshots").mkdir(exist_ok=True)

        self._session = SessionInfo(
            session_id=session_id,
            name=name,
            started_at=now.isoformat(),
            session_dir=str(session_dir),
        )
        self._session_dir = session_dir
        self._actions = []
        self._action_counter = 0

        # Save initial session info
        self._save_session_info()

        logger.info(f"Started session '{name}' ({session_id}) in {session_dir}")
        return session_id

    def end_session(self) -> Optional[SessionInfo]:
        """
        End the current logging session.

        Saves final session metadata and returns session info.

        Returns:
            SessionInfo for the completed session, or None if no active session.
        """
        if self._session is None:
            return None

        self._session.ended_at = datetime.now().isoformat()
        self._session.total_actions = len(self._actions)
        self._session.successful_actions = sum(
            1 for a in self._actions if a.status == ActionStatus.SUCCESS.value
        )
        self._session.failed_actions = sum(
            1 for a in self._actions if a.status == ActionStatus.FAILURE.value
        )

        # Save final session info and actions
        self._save_session_info()
        self._save_actions()

        session = self._session
        logger.info(
            f"Ended session '{session.name}' ({session.session_id}): "
            f"{session.successful_actions}/{session.total_actions} successful"
        )

        # Clear session state
        self._session = None
        self._session_dir = None
        self._actions = []

        return session

    def log_action(
        self,
        action_type: Union[ActionType, str],
        target: str,
        details: Optional[Dict[str, Any]] = None,
        capture_before: bool = True,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        """
        Log the start of a GUI action.

        Creates a new action log entry and optionally captures a
        before screenshot.

        Args:
            action_type: Type of action being performed.
            target: Description of the target element/location.
            details: Additional action details (app name, method, etc.).
            capture_before: If True, capture screenshot before action.
            x: X coordinate (if applicable).
            y: Y coordinate (if applicable).

        Returns:
            Action ID for use with complete_action().

        Raises:
            RuntimeError: If no session is active.
        """
        if self._session is None:
            raise RuntimeError("No active session. Call start_session() first.")

        # Generate action ID
        self._action_counter += 1
        action_id = f"action_{self._action_counter:04d}"

        # Normalize action type
        if isinstance(action_type, ActionType):
            action_type_str = action_type.value
        else:
            action_type_str = str(action_type)

        # Create action entry
        now = datetime.now()
        action = ActionLogEntry(
            action_id=action_id,
            action_type=action_type_str,
            target=target,
            status=ActionStatus.IN_PROGRESS.value,
            timestamp_start=now.isoformat(),
            details=details or {},
            x=x,
            y=y,
        )

        # Capture before screenshot
        if capture_before and self._enable_screenshots:
            screenshot_path = self._capture_screenshot(f"before_{action_id}")
            if screenshot_path:
                action.before_screenshot = screenshot_path

        self._actions.append(action)
        logger.debug(f"Logged action: {action_type_str} on '{target}' ({action_id})")

        return action_id

    def complete_action(
        self,
        action_id: str,
        success: bool,
        capture_after: bool = True,
        result_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ActionLogEntry]:
        """
        Mark an action as complete.

        Updates the action with result information and optionally
        captures an after screenshot.

        Args:
            action_id: ID returned from log_action().
            success: Whether the action succeeded.
            capture_after: If True, capture screenshot after action.
            result_details: Additional result information.
            error_message: Error message if action failed.

        Returns:
            Updated ActionLogEntry, or None if action not found.
        """
        # Find the action
        action = self._find_action(action_id)
        if action is None:
            logger.warning(f"Action not found: {action_id}")
            return None

        # Update action
        now = datetime.now()
        action.timestamp_end = now.isoformat()
        action.status = ActionStatus.SUCCESS.value if success else ActionStatus.FAILURE.value
        action.result_details = result_details or {}
        action.error_message = error_message

        # Calculate duration
        try:
            start = datetime.fromisoformat(action.timestamp_start)
            action.duration_ms = int((now - start).total_seconds() * 1000)
        except (ValueError, TypeError):
            action.duration_ms = 0

        # Capture after screenshot
        if capture_after and self._enable_screenshots:
            screenshot_path = self._capture_screenshot(f"after_{action_id}")
            if screenshot_path:
                action.after_screenshot = screenshot_path

        # Save actions incrementally
        self._save_actions()

        status_str = "succeeded" if success else "failed"
        logger.debug(f"Action {action_id} {status_str} (duration: {action.duration_ms}ms)")

        return action

    def log_quick_action(
        self,
        action_type: Union[ActionType, str],
        target: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        result_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        capture_before: bool = True,
        capture_after: bool = True,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        """
        Log a complete action in one call.

        Convenience method for actions that complete immediately.

        Args:
            action_type: Type of action.
            target: Target element description.
            success: Whether action succeeded.
            details: Action details.
            result_details: Result details.
            error_message: Error message if failed.
            capture_before: Capture before screenshot.
            capture_after: Capture after screenshot.
            x: X coordinate (if applicable).
            y: Y coordinate (if applicable).

        Returns:
            Action ID.
        """
        action_id = self.log_action(
            action_type=action_type,
            target=target,
            details=details,
            capture_before=capture_before,
            x=x,
            y=y,
        )
        self.complete_action(
            action_id=action_id,
            success=success,
            capture_after=capture_after,
            result_details=result_details,
            error_message=error_message,
        )
        return action_id

    def generate_report(
        self,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """
        Generate an HTML report with screenshot timeline.

        Creates a visual report showing all actions with their
        before/after screenshots for debugging.

        Args:
            output_path: Custom output path. Defaults to session_dir/report.html

        Returns:
            Path to generated report, or None if generation failed.
        """
        session_dir = self._session_dir
        if session_dir is None:
            # Try to use most recent session
            sessions = self.list_sessions()
            if not sessions:
                logger.warning("No sessions available for report generation")
                return None
            session_dir = Path(sessions[0]["session_dir"])

        # Determine output path
        if output_path is None:
            output_path = session_dir / "report.html"
        else:
            output_path = Path(output_path)

        # Load actions if not in memory
        actions = self._actions
        if not actions:
            actions_file = session_dir / "actions.json"
            if actions_file.exists():
                with open(actions_file, "r") as f:
                    actions_data = json.load(f)
                    actions = [ActionLogEntry(**a) for a in actions_data.get("actions", [])]

        # Load session info
        session_info: Dict[str, Any] = {}
        session_file = session_dir / "session.json"
        if session_file.exists():
            with open(session_file, "r") as f:
                session_info = json.load(f)

        # Generate HTML
        html = self._generate_html_report(session_info, actions, session_dir)

        # Write report
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Generated report: {output_path}")

        return output_path

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all available logging sessions.

        Returns:
            List of session info dictionaries, sorted by date (newest first).
        """
        sessions = []

        if not self._base_dir.exists():
            return sessions

        for session_dir in sorted(self._base_dir.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue

            session_file = session_dir / "session.json"
            if session_file.exists():
                try:
                    with open(session_file, "r") as f:
                        session_info = json.load(f)
                        sessions.append(session_info)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to read session {session_dir.name}: {e}")

        return sessions

    def export_session(
        self,
        session_id: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
        include_screenshots: bool = True,
    ) -> Optional[Path]:
        """
        Export a session as a ZIP archive for sharing.

        Args:
            session_id: Session to export. Defaults to current/most recent.
            output_path: Output ZIP path. Defaults to session_id.zip in base_dir.
            include_screenshots: Include screenshot images in export.

        Returns:
            Path to exported ZIP, or None if export failed.
        """
        # Determine session directory
        if session_id:
            session_dir = self._base_dir / session_id
        elif self._session_dir:
            session_dir = self._session_dir
        else:
            sessions = self.list_sessions()
            if not sessions:
                logger.warning("No sessions available for export")
                return None
            session_dir = Path(sessions[0]["session_dir"])

        if not session_dir.exists():
            logger.warning(f"Session directory not found: {session_dir}")
            return None

        # Determine output path
        if output_path is None:
            output_path = self._base_dir / f"{session_dir.name}.zip"
        else:
            output_path = Path(output_path)

        # Create ZIP archive
        try:
            import zipfile

            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in session_dir.rglob("*"):
                    if file_path.is_file():
                        # Skip screenshots if not included
                        if not include_screenshots and file_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                            continue

                        rel_path = file_path.relative_to(session_dir)
                        zf.write(file_path, rel_path)

            logger.info(f"Exported session to: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return None

    def cleanup_old_sessions(self, keep_count: Optional[int] = None) -> int:
        """
        Remove old sessions to free disk space.

        Args:
            keep_count: Number of sessions to keep. Defaults to max_sessions.

        Returns:
            Number of sessions removed.
        """
        if keep_count is None:
            keep_count = self._max_sessions

        sessions = self.list_sessions()
        removed = 0

        for session_info in sessions[keep_count:]:
            session_dir = Path(session_info.get("session_dir", ""))
            if session_dir.exists():
                try:
                    shutil.rmtree(session_dir)
                    removed += 1
                    logger.debug(f"Removed old session: {session_dir.name}")
                except OSError as e:
                    logger.warning(f"Failed to remove session {session_dir.name}: {e}")

        if removed > 0:
            logger.info(f"Cleaned up {removed} old session(s)")

        return removed

    @property
    def session_active(self) -> bool:
        """Check if a session is currently active."""
        return self._session is not None

    @property
    def current_session(self) -> Optional[SessionInfo]:
        """Get current session info."""
        return self._session

    @property
    def current_session_dir(self) -> Optional[Path]:
        """Get current session directory."""
        return self._session_dir

    @property
    def screenshots_enabled(self) -> bool:
        """Check if screenshot capture is enabled."""
        return self._enable_screenshots and self._capture is not None

    def disable_screenshots(self) -> None:
        """Disable screenshot capture for this logger."""
        self._enable_screenshots = False

    def enable_screenshots(self) -> None:
        """Enable screenshot capture for this logger."""
        self._enable_screenshots = True
        if self._capture is None and SCREENSHOT_CAPTURE_AVAILABLE and MultiMonitorCapture is not None:
            try:
                self._capture = MultiMonitorCapture()
            except Exception as e:
                logger.warning(f"Failed to initialize screenshot capture: {e}")

    def _find_action(self, action_id: str) -> Optional[ActionLogEntry]:
        """Find an action by ID."""
        for action in self._actions:
            if action.action_id == action_id:
                return action
        return None

    def _capture_screenshot(self, name: str) -> Optional[str]:
        """Capture a screenshot and save to session directory."""
        if not self._enable_screenshots or self._capture is None:
            return None

        if self._session_dir is None:
            return None

        try:
            result = self._capture.capture_all_displays()

            # Save screenshot
            screenshots_dir = self._session_dir / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)

            filename = f"{name}.{self._screenshot_format}"
            filepath = screenshots_dir / filename
            filepath.write_bytes(result.image_bytes)

            # Return relative path
            return str(Path("screenshots") / filename)

        except Exception as e:
            logger.warning(f"Failed to capture screenshot '{name}': {e}")
            return None

    def _save_session_info(self) -> None:
        """Save session info to JSON file."""
        if self._session is None or self._session_dir is None:
            return

        session_file = self._session_dir / "session.json"
        with open(session_file, "w") as f:
            json.dump(self._session.to_dict(), f, indent=2)

    def _save_actions(self) -> None:
        """Save actions to JSON file."""
        if self._session_dir is None:
            return

        actions_file = self._session_dir / "actions.json"
        with open(actions_file, "w") as f:
            json.dump(
                {
                    "session_id": self._session.session_id if self._session else "",
                    "actions": [a.to_dict() for a in self._actions],
                },
                f,
                indent=2,
            )

    def _rotate_sessions(self) -> None:
        """Rotate old sessions if necessary."""
        if self._max_sessions <= 0:
            return  # Rotation disabled

        sessions = self.list_sessions()
        if len(sessions) >= self._max_sessions:
            # Remove oldest sessions to make room for new one
            self.cleanup_old_sessions(self._max_sessions - 1)

    def _generate_html_report(
        self,
        session_info: Dict[str, Any],
        actions: List[ActionLogEntry],
        _session_dir: Path,
    ) -> str:
        """Generate HTML report content."""
        session_name = escape(session_info.get("name", "Session"))
        session_id = escape(session_info.get("session_id", ""))
        started_at = session_info.get("started_at", "")
        ended_at = session_info.get("ended_at", "")
        total = session_info.get("total_actions", len(actions))
        successful = session_info.get("successful_actions", sum(1 for a in actions if a.status == ActionStatus.SUCCESS.value))
        failed = session_info.get("failed_actions", sum(1 for a in actions if a.status == ActionStatus.FAILURE.value))

        # Format timestamps
        try:
            started_dt = datetime.fromisoformat(started_at)
            started_str = started_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            started_str = started_at

        try:
            ended_dt = datetime.fromisoformat(ended_at) if ended_at else None
            ended_str = ended_dt.strftime("%Y-%m-%d %H:%M:%S") if ended_dt else "In Progress"
        except (ValueError, TypeError):
            ended_str = ended_at or "In Progress"

        # Generate action rows
        action_rows = []
        for action in actions:
            status_class = "success" if action.status == ActionStatus.SUCCESS.value else "failure"
            if action.status in (ActionStatus.PENDING.value, ActionStatus.IN_PROGRESS.value):
                status_class = "pending"

            before_img = ""
            if action.before_screenshot:
                before_img = f'<a href="{escape(action.before_screenshot)}" target="_blank"><img src="{escape(action.before_screenshot)}" alt="Before" class="thumbnail"></a>'

            after_img = ""
            if action.after_screenshot:
                after_img = f'<a href="{escape(action.after_screenshot)}" target="_blank"><img src="{escape(action.after_screenshot)}" alt="After" class="thumbnail"></a>'

            coords = ""
            if action.x is not None and action.y is not None:
                coords = f"({int(action.x)}, {int(action.y)})"

            error_display = ""
            if action.error_message:
                error_display = f'<div class="error-message">{escape(action.error_message)}</div>'

            details_str = ""
            if action.details:
                details_str = ", ".join(f"{k}={v}" for k, v in action.details.items())

            action_rows.append(f"""
            <tr class="{status_class}">
                <td class="action-id">{escape(action.action_id)}</td>
                <td>{escape(action.action_type)}</td>
                <td class="target">{escape(action.target)}</td>
                <td class="status">{escape(action.status)}</td>
                <td>{action.duration_ms}ms</td>
                <td class="coords">{coords}</td>
                <td class="screenshots">{before_img}</td>
                <td class="screenshots">{after_img}</td>
                <td class="details">{escape(details_str)}{error_display}</td>
            </tr>
            """)

        actions_html = "\n".join(action_rows)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Action Log: {session_name}</title>
    <style>
        :root {{
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --text-color: #eee;
            --text-muted: #888;
            --success-color: #4ade80;
            --failure-color: #f87171;
            --pending-color: #fbbf24;
            --accent-color: #818cf8;
            --border-color: #374151;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            line-height: 1.5;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        h1 {{
            color: var(--accent-color);
            margin-bottom: 10px;
        }}

        .session-info {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}

        .info-item {{
            display: flex;
            flex-direction: column;
        }}

        .info-label {{
            color: var(--text-muted);
            font-size: 0.85em;
            margin-bottom: 4px;
        }}

        .info-value {{
            font-weight: 500;
        }}

        .summary-stats {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}

        .stat {{
            background: var(--card-bg);
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
        }}

        .stat-value {{
            font-size: 2em;
            font-weight: bold;
        }}

        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9em;
        }}

        .stat.success .stat-value {{ color: var(--success-color); }}
        .stat.failure .stat-value {{ color: var(--failure-color); }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
        }}

        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background: rgba(0, 0, 0, 0.2);
            font-weight: 600;
            color: var(--text-muted);
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        tr.success {{ background: rgba(74, 222, 128, 0.05); }}
        tr.failure {{ background: rgba(248, 113, 113, 0.1); }}
        tr.pending {{ background: rgba(251, 191, 36, 0.05); }}

        tr:hover {{ background: rgba(255, 255, 255, 0.05); }}

        .action-id {{
            font-family: monospace;
            color: var(--text-muted);
        }}

        .target {{
            max-width: 250px;
            word-wrap: break-word;
        }}

        .status {{
            font-weight: 500;
        }}

        tr.success .status {{ color: var(--success-color); }}
        tr.failure .status {{ color: var(--failure-color); }}
        tr.pending .status {{ color: var(--pending-color); }}

        .coords {{
            font-family: monospace;
            color: var(--text-muted);
        }}

        .screenshots {{
            width: 120px;
        }}

        .thumbnail {{
            max-width: 100px;
            max-height: 60px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            cursor: pointer;
            transition: transform 0.2s;
        }}

        .thumbnail:hover {{
            transform: scale(1.5);
            z-index: 10;
            position: relative;
        }}

        .details {{
            font-size: 0.9em;
            color: var(--text-muted);
            max-width: 200px;
            word-wrap: break-word;
        }}

        .error-message {{
            color: var(--failure-color);
            margin-top: 4px;
            font-size: 0.85em;
        }}

        .no-actions {{
            text-align: center;
            color: var(--text-muted);
            padding: 40px;
        }}

        footer {{
            text-align: center;
            margin-top: 30px;
            color: var(--text-muted);
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Action Log: {session_name}</h1>

        <div class="session-info">
            <div class="info-item">
                <span class="info-label">Session ID</span>
                <span class="info-value">{session_id}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Started</span>
                <span class="info-value">{started_str}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Ended</span>
                <span class="info-value">{ended_str}</span>
            </div>
        </div>

        <div class="summary-stats">
            <div class="stat">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Actions</div>
            </div>
            <div class="stat success">
                <div class="stat-value">{successful}</div>
                <div class="stat-label">Successful</div>
            </div>
            <div class="stat failure">
                <div class="stat-value">{failed}</div>
                <div class="stat-label">Failed</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Coords</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                {actions_html if actions_html else '<tr><td colspan="9" class="no-actions">No actions recorded</td></tr>'}
            </tbody>
        </table>

        <footer>
            Generated by claude-loop Action Logger
        </footer>
    </div>
</body>
</html>
"""


# Convenience functions

def create_action_logger(
    base_dir: Optional[Union[str, Path]] = None,
    enable_screenshots: bool = True,
    max_sessions: int = ActionLogger.DEFAULT_MAX_SESSIONS,
) -> ActionLogger:
    """
    Create a new ActionLogger instance.

    Args:
        base_dir: Base directory for sessions.
        enable_screenshots: Enable screenshot capture.
        max_sessions: Maximum sessions to keep.

    Returns:
        Configured ActionLogger instance.
    """
    return ActionLogger(
        base_dir=base_dir,
        enable_screenshots=enable_screenshots,
        max_sessions=max_sessions,
    )


def get_latest_session_report() -> Optional[Path]:
    """
    Get path to the most recent session's HTML report.

    Returns:
        Path to report.html, or None if no sessions exist.
    """
    base_dir = DEFAULT_SCREENSHOTS_BASE
    if not base_dir.exists():
        return None

    for session_dir in sorted(base_dir.iterdir(), reverse=True):
        if session_dir.is_dir():
            report_path = session_dir / "report.html"
            if report_path.exists():
                return report_path

    return None


def list_all_sessions(base_dir: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """
    List all available logging sessions.

    Args:
        base_dir: Base directory to search.

    Returns:
        List of session info dictionaries.
    """
    logger_instance = ActionLogger(base_dir=base_dir, enable_screenshots=False)
    return logger_instance.list_sessions()


def cleanup_sessions(keep_count: int = ActionLogger.DEFAULT_MAX_SESSIONS) -> int:
    """
    Clean up old logging sessions.

    Args:
        keep_count: Number of sessions to keep.

    Returns:
        Number of sessions removed.
    """
    logger_instance = ActionLogger(enable_screenshots=False)
    return logger_instance.cleanup_old_sessions(keep_count)


# Module availability flag
ACTION_LOGGER_AVAILABLE = True

__all__ = [
    # Main class
    "ActionLogger",
    # Data classes
    "ActionLogEntry",
    "SessionInfo",
    # Enums
    "ActionType",
    "ActionStatus",
    # Convenience functions
    "create_action_logger",
    "get_latest_session_report",
    "list_all_sessions",
    "cleanup_sessions",
    # Constants
    "DEFAULT_SCREENSHOTS_BASE",
    "ACTION_LOGGER_AVAILABLE",
]
