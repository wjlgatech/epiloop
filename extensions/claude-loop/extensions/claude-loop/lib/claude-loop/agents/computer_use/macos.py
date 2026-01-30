"""
macOS automation module using AppleScript/osascript.

This module provides macOS application automation capabilities for claude-loop,
enabling control of native apps like Unity, Finder, and others through AppleScript
with built-in safety features like human checkpoints for permission dialogs.

Example:
    async with MacOSAgent() as macos:
        await macos.activate_app("Unity")
        await macos.menu_click("Unity", ["File", "Build Settings..."])
        await macos.keyboard_shortcut("command", "s")
"""

import asyncio
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import ActionLog, ActionResult, HumanCheckpoint


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class MacOSConfig:
    """Configuration for MacOSAgent."""

    timeout_seconds: int = 30
    """Default timeout for actions in seconds."""

    log_dir: str = ".claude-loop/computer-use-logs"
    """Directory for action logs and screenshots."""

    screenshot_all_actions: bool = True
    """Capture screenshots before/after all actions."""

    max_retries: int = 3
    """Maximum retry attempts for failed actions."""

    retry_base_delay_seconds: float = 1.0
    """Base delay for exponential backoff in seconds."""

    enable_human_checkpoints: bool = True
    """Auto-detect and trigger human checkpoints for permission dialogs."""

    typing_delay_ms: int = 50
    """Delay between keystrokes when typing (milliseconds)."""

    # Permission dialog detection patterns
    permission_dialog_apps: list[str] = field(
        default_factory=lambda: [
            "System Preferences",
            "System Settings",
            "SecurityAgent",
        ]
    )


# =============================================================================
# AppleScript Helpers
# =============================================================================


def _run_osascript(script: str, timeout: int = 30) -> tuple[bool, str, str]:
    """
    Execute AppleScript via osascript.

    Args:
        script: AppleScript code to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        Tuple of (success, stdout, stderr).
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (
            result.returncode == 0,
            result.stdout.strip(),
            result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return False, "", "AppleScript execution timed out"
    except Exception as e:
        return False, "", str(e)


async def _run_osascript_async(
    script: str,
    timeout: int = 30,
) -> tuple[bool, str, str]:
    """Execute AppleScript asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_osascript, script, timeout)


def _escape_applescript_string(text: str) -> str:
    """Escape a string for use in AppleScript."""
    # Escape backslashes first, then quotes
    return text.replace("\\", "\\\\").replace('"', '\\"')


# =============================================================================
# macOS Agent
# =============================================================================


class MacOSAgent:
    """
    macOS automation agent using AppleScript/osascript.

    Provides async methods for macOS app control with built-in safety features:
    - Detection of permission dialogs for human checkpoints
    - Screenshot logging before/after actions
    - Retry logic with exponential backoff
    - Comprehensive action logging

    Usage:
        async with MacOSAgent() as macos:
            result = await macos.activate_app("Unity")
            if result.succeeded:
                await macos.menu_click("Unity", ["File", "Save"])

    Attributes:
        config: MacOSConfig with agent settings.
        session_id: Unique session identifier for logging.
    """

    def __init__(
        self,
        config: MacOSConfig | None = None,
        timeout: int = 30,
    ):
        """
        Initialize MacOSAgent.

        Args:
            config: Full configuration object. If provided, timeout arg ignored.
            timeout: Default timeout for actions in seconds.
        """
        if config:
            self.config = config
        else:
            self.config = MacOSConfig(timeout_seconds=timeout)

        self.session_id = f"macos_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self._action_log: list[ActionLog] = []
        self._action_counter = 0
        self._log_dir: Path | None = None
        self._human_callback: Callable[[HumanCheckpoint], Any] | None = None
        self._initialized = False

    async def __aenter__(self) -> "MacOSAgent":
        """Async context manager entry."""
        await self._start()
        return self

    async def __aexit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def _start(self) -> None:
        """Initialize the agent."""
        # Verify we're on macOS
        import platform

        if platform.system() != "Darwin":
            raise RuntimeError("MacOSAgent requires macOS")

        # Initialize log directory
        self._log_dir = Path(self.config.log_dir) / self.session_id
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Verify osascript is available
        success, _, error = await _run_osascript_async('return "ok"', timeout=5)
        if not success:
            raise RuntimeError(f"osascript not available: {error}")

        self._initialized = True

    async def close(self) -> None:
        """Clean up resources and save action log."""
        # Save action log
        if self._action_log and self._log_dir:
            log_file = self._log_dir / "actions.json"
            with open(log_file, "w") as f:
                json.dump([a.to_dict() for a in self._action_log], f, indent=2)

        self._initialized = False

    # -------------------------------------------------------------------------
    # App Control Actions
    # -------------------------------------------------------------------------

    async def activate_app(self, app_name: str) -> ActionResult:
        """
        Bring application to foreground, launch if not running.

        Args:
            app_name: Name of the application (e.g., "Unity", "Finder").

        Returns:
            ActionResult with status.
        """
        escaped_name = _escape_applescript_string(app_name)
        script = f'''
tell application "{escaped_name}"
    activate
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                # Wait a moment for app to activate
                await asyncio.sleep(0.5)

                # Check for permission dialog
                if self.config.enable_human_checkpoints:
                    checkpoint = await self._check_for_permission_dialog()
                    if checkpoint:
                        return ActionResult.human_needed(
                            checkpoint.instructions,
                            screenshot_path=checkpoint.screenshot_path,
                        )

                return ActionResult.success(
                    data={"app": app_name},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to activate {app_name}: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "activate_app",
            {"app_name": app_name},
            action,
        )

    async def get_frontmost_app(self) -> ActionResult:
        """
        Get the name of the currently active (frontmost) application.

        Returns:
            ActionResult with app name in data["app"].
        """
        script = '''
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    return frontApp
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, stdout, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                return ActionResult.success(
                    data={"app": stdout},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to get frontmost app: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "get_frontmost_app",
            {},
            action,
        )

    # -------------------------------------------------------------------------
    # Menu Actions
    # -------------------------------------------------------------------------

    async def menu_click(
        self,
        app_name: str,
        menu_path: list[str],
    ) -> ActionResult:
        """
        Click through a menu hierarchy.

        Args:
            app_name: Name of the application.
            menu_path: List of menu items to click through.
                       e.g., ["File", "Export", "As PDF..."]

        Returns:
            ActionResult with status.
        """
        if not menu_path:
            return ActionResult.failure("Menu path cannot be empty")

        escaped_app = _escape_applescript_string(app_name)

        # Build menu path navigation
        menu_nav = ""
        for i, item in enumerate(menu_path):
            escaped_item = _escape_applescript_string(item)
            if i == 0:
                menu_nav = f'menu bar item "{escaped_item}" of menu bar 1'
            else:
                menu_nav = f'menu item "{escaped_item}" of menu of {menu_nav}'

        script = f'''
tell application "{escaped_app}" to activate
delay 0.3
tell application "System Events"
    tell process "{escaped_app}"
        click {menu_nav}
    end tell
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                # Wait for menu action to complete
                await asyncio.sleep(0.5)

                # Check for dialog/permission popup
                if self.config.enable_human_checkpoints:
                    checkpoint = await self._check_for_permission_dialog()
                    if checkpoint:
                        return ActionResult.human_needed(
                            checkpoint.instructions,
                            screenshot_path=checkpoint.screenshot_path,
                        )

                return ActionResult.success(
                    data={"app": app_name, "menu_path": menu_path},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to click menu {' > '.join(menu_path)}: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "menu_click",
            {"app_name": app_name, "menu_path": menu_path},
            action,
        )

    # -------------------------------------------------------------------------
    # Input Actions
    # -------------------------------------------------------------------------

    async def keyboard_shortcut(self, *keys: str) -> ActionResult:
        """
        Send a keyboard shortcut.

        Args:
            keys: Key names to press together.
                  e.g., ("command", "shift", "s") for Cmd+Shift+S

        Supported modifiers:
            - command, cmd
            - shift
            - option, alt
            - control, ctrl

        Returns:
            ActionResult with status.
        """
        if not keys:
            return ActionResult.failure("No keys specified")

        # Map key names to AppleScript key codes/names
        key_mapping = {
            "command": "command down",
            "cmd": "command down",
            "shift": "shift down",
            "option": "option down",
            "alt": "option down",
            "control": "control down",
            "ctrl": "control down",
        }

        modifiers = []
        main_key = None

        for key in keys:
            lower_key = key.lower()
            if lower_key in key_mapping:
                modifiers.append(key_mapping[lower_key])
            else:
                main_key = key

        if not main_key:
            return ActionResult.failure("No main key specified (only modifiers)")

        # Build keystroke command
        if modifiers:
            modifier_str = ", ".join(modifiers)
            escaped_key = _escape_applescript_string(main_key)
            script = f'''
tell application "System Events"
    keystroke "{escaped_key}" using {{{modifier_str}}}
end tell
'''
        else:
            escaped_key = _escape_applescript_string(main_key)
            script = f'''
tell application "System Events"
    keystroke "{escaped_key}"
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                await asyncio.sleep(0.3)
                return ActionResult.success(
                    data={"keys": list(keys)},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to send keyboard shortcut: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "keyboard_shortcut",
            {"keys": list(keys)},
            action,
        )

    async def type_text(self, text: str) -> ActionResult:
        """
        Type text at the current cursor position.

        Args:
            text: Text to type.

        Returns:
            ActionResult with status.
        """
        escaped_text = _escape_applescript_string(text)

        # Use keystroke for typing with optional delay between characters
        delay = self.config.typing_delay_ms / 1000.0
        script = f'''
tell application "System Events"
    keystroke "{escaped_text}"
end tell
'''

        # For longer text, use character-by-character with delay
        if len(text) > 50 and delay > 0:
            # Build script that types character by character
            char_scripts = []
            for char in text:
                escaped_char = _escape_applescript_string(char)
                char_scripts.append(f'keystroke "{escaped_char}"')
                char_scripts.append(f"delay {delay}")
            script = f'''
tell application "System Events"
    {chr(10).join(char_scripts)}
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds + len(text) // 10
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                return ActionResult.success(
                    data={"text_length": len(text)},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to type text: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "type_text",
            {"text_length": len(text)},
            action,
        )

    # -------------------------------------------------------------------------
    # Window Actions
    # -------------------------------------------------------------------------

    async def wait_for_window(
        self,
        title_contains: str,
        app_name: str | None = None,
        timeout: int | None = None,
    ) -> ActionResult:
        """
        Wait for a window with a title containing the specified text.

        Args:
            title_contains: Substring to search for in window title.
            app_name: Limit search to specific app (optional).
            timeout: Override default timeout (seconds).

        Returns:
            ActionResult with window info in data.
        """
        timeout_seconds = timeout or self.config.timeout_seconds
        escaped_title = _escape_applescript_string(title_contains)

        if app_name:
            escaped_app = _escape_applescript_string(app_name)
            script = f'''
tell application "System Events"
    tell process "{escaped_app}"
        repeat with w in windows
            if name of w contains "{escaped_title}" then
                return name of w
            end if
        end repeat
    end tell
end tell
return ""
'''
        else:
            script = f'''
tell application "System Events"
    repeat with proc in (every process whose visible is true)
        try
            repeat with w in windows of proc
                if name of w contains "{escaped_title}" then
                    return name of w & " (" & name of proc & ")"
                end if
            end repeat
        end try
    end repeat
end tell
return ""
'''

        async def action() -> ActionResult:
            start_time = time.time()
            poll_interval = 0.5

            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    return ActionResult.timeout(
                        f"Window containing '{title_contains}' not found",
                        duration_ms=int(elapsed * 1000),
                    )

                success, stdout, _ = await _run_osascript_async(script, 5)

                if success and stdout:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ActionResult.success(
                        data={
                            "window_title": stdout,
                            "search_term": title_contains,
                        },
                        duration_ms=duration_ms,
                    )

                await asyncio.sleep(poll_interval)

        return await self._execute_with_logging(
            "wait_for_window",
            {
                "title_contains": title_contains,
                "app_name": app_name,
                "timeout": timeout_seconds,
            },
            action,
        )

    async def screenshot(
        self,
        path: str | None = None,
        window: str | None = None,
    ) -> ActionResult:
        """
        Capture a screenshot of the screen or a specific window.

        Args:
            path: Path to save screenshot. Auto-generated if not provided.
            window: Window title to capture (captures full screen if not specified).

        Returns:
            ActionResult with screenshot path in data.
        """

        async def action() -> ActionResult:
            start_time = time.time()

            # Determine screenshot path
            if path:
                screenshot_path = path
            elif self._log_dir:
                timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
                filename = f"{self._action_counter:04d}_screenshot_{timestamp}.png"
                screenshot_path = str(self._log_dir / filename)
            else:
                screenshot_path = f"/tmp/macos_screenshot_{uuid.uuid4().hex[:8]}.png"

            # Build screencapture command
            if window:
                # Capture specific window by title
                # First, find the window bounds
                escaped_window = _escape_applescript_string(window)
                find_script = f'''
tell application "System Events"
    repeat with proc in (every process whose visible is true)
        try
            repeat with w in windows of proc
                if name of w contains "{escaped_window}" then
                    set winPos to position of w
                    set winSize to size of w
                    return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
                end if
            end repeat
        end try
    end repeat
end tell
return ""
'''
                success, stdout, error = await _run_osascript_async(find_script, 5)
                if not success or not stdout:
                    return ActionResult.failure(
                        f"Window '{window}' not found for screenshot: {error}"
                    )

                # Parse bounds: x,y,width,height
                try:
                    parts = stdout.split(",")
                    x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                    # Use screencapture with region
                    cmd = ["screencapture", "-R", f"{x},{y},{w},{h}", screenshot_path]
                except (IndexError, ValueError):
                    return ActionResult.failure(f"Invalid window bounds: {stdout}")
            else:
                # Full screen capture
                cmd = ["screencapture", "-x", screenshot_path]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=10,
                )
                duration_ms = int((time.time() - start_time) * 1000)

                if result.returncode == 0:
                    return ActionResult.success(
                        data={"path": screenshot_path, "window": window},
                        screenshot_path=screenshot_path,
                        duration_ms=duration_ms,
                    )
                else:
                    return ActionResult.failure(
                        f"Screenshot failed: {result.stderr.decode()}",
                        duration_ms=duration_ms,
                    )
            except subprocess.TimeoutExpired:
                return ActionResult.timeout("Screenshot capture timed out")
            except Exception as e:
                return ActionResult.failure(f"Screenshot failed: {e}")

        # Screenshot doesn't need the standard logging wrapper (would be recursive)
        return await action()

    # -------------------------------------------------------------------------
    # Finder Actions
    # -------------------------------------------------------------------------

    async def finder_open(self, path: str) -> ActionResult:
        """
        Open a file or folder in Finder.

        Args:
            path: Path to open. Can be file or directory.

        Returns:
            ActionResult with status.
        """
        # Expand user path and verify it exists
        expanded_path = Path(path).expanduser().resolve()
        if not expanded_path.exists():
            return ActionResult.failure(f"Path does not exist: {path}")

        posix_path = str(expanded_path)
        escaped_path = _escape_applescript_string(posix_path)

        script = f'''
tell application "Finder"
    activate
    open POSIX file "{escaped_path}"
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                await asyncio.sleep(0.5)
                return ActionResult.success(
                    data={"path": posix_path},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to open in Finder: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "finder_open",
            {"path": posix_path},
            action,
        )

    async def finder_select(self, paths: list[str]) -> ActionResult:
        """
        Select files or folders in Finder.

        Args:
            paths: List of paths to select.

        Returns:
            ActionResult with status.
        """
        if not paths:
            return ActionResult.failure("No paths specified")

        # Expand and verify paths
        expanded_paths = []
        for path in paths:
            exp = Path(path).expanduser().resolve()
            if not exp.exists():
                return ActionResult.failure(f"Path does not exist: {path}")
            expanded_paths.append(str(exp))

        # Build list of POSIX files for AppleScript
        posix_files = ", ".join(
            f'POSIX file "{_escape_applescript_string(p)}"'
            for p in expanded_paths
        )

        # Reveal in Finder and select
        first_path = expanded_paths[0]
        escaped_first = _escape_applescript_string(first_path)
        script = f'''
tell application "Finder"
    activate
    reveal POSIX file "{escaped_first}"
    select {{{posix_files}}}
end tell
'''

        async def action() -> ActionResult:
            start_time = time.time()
            success, _, error = await _run_osascript_async(
                script, self.config.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if success:
                await asyncio.sleep(0.5)
                return ActionResult.success(
                    data={"paths": expanded_paths, "count": len(expanded_paths)},
                    duration_ms=duration_ms,
                )
            else:
                return ActionResult.failure(
                    f"Failed to select in Finder: {error}",
                    duration_ms=duration_ms,
                )

        return await self._execute_with_logging(
            "finder_select",
            {"paths": expanded_paths},
            action,
        )

    # -------------------------------------------------------------------------
    # Human Checkpoint
    # -------------------------------------------------------------------------

    async def wait_for_human(
        self,
        reason: str,
        instructions: str,
        timeout: int = 300,
    ) -> ActionResult:
        """
        Pause execution and wait for human intervention.

        Args:
            reason: Category of intervention (permission, error, etc.).
            instructions: Clear instructions for what the human should do.
            timeout: Maximum time to wait in seconds (default 5 minutes).

        Returns:
            ActionResult with SUCCESS if human completed action, TIMEOUT otherwise.
        """
        screenshot_path = None
        if self._log_dir:
            screenshot_result = await self.screenshot()
            if screenshot_result.succeeded:
                screenshot_path = screenshot_result.data.get("path")

        checkpoint = HumanCheckpoint(
            reason=reason,
            instructions=instructions,
            screenshot_path=screenshot_path,
            timeout_seconds=timeout,
        )

        # Log the checkpoint
        self._log_action(
            "wait_for_human",
            {"reason": reason, "instructions": instructions},
            ActionResult.human_needed(instructions, screenshot_path=screenshot_path),
            screenshot_before=screenshot_path,
        )

        # Notify via callback if registered
        if self._human_callback:
            self._human_callback(checkpoint)

        # Display checkpoint info
        print(f"\n{'='*60}")
        print(f"HUMAN CHECKPOINT: {reason.upper()}")
        print(f"{'='*60}")
        print(f"Instructions: {instructions}")
        if screenshot_path:
            print(f"Screenshot saved: {screenshot_path}")
        print(f"Timeout: {timeout} seconds")
        print(f"{'='*60}")
        print("Press ENTER when complete, or wait for timeout...")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Wait for human to complete (simple polling approach)
        try:
            elapsed = 0
            poll_interval = 5  # seconds

            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed = int(time.time() - start_time)

            duration_ms = int((time.time() - start_time) * 1000)
            return ActionResult.timeout(
                f"Human checkpoint timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            duration_ms = int((time.time() - start_time) * 1000)
            return ActionResult.success(
                data={"reason": reason, "completed_by": "human"},
                duration_ms=duration_ms,
            )

    def set_human_callback(
        self,
        callback: Callable[[HumanCheckpoint], Any],
    ) -> None:
        """
        Set callback for human checkpoint notifications.

        Args:
            callback: Function called when human intervention needed.
        """
        self._human_callback = callback

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def get_action_log(self) -> list[ActionLog]:
        """Get log of all executed actions."""
        return self._action_log.copy()

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    async def _capture_screenshot(self, action_name: str) -> str | None:
        """Capture screenshot and return path."""
        if not self._log_dir:
            return None

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        filename = f"{self._action_counter:04d}_{action_name}_{timestamp}.png"
        path = str(self._log_dir / filename)

        result = await self.screenshot(path=path)
        return path if result.succeeded else None

    async def _check_for_permission_dialog(self) -> HumanCheckpoint | None:
        """Check if a permission dialog is present."""
        # Check if a permission dialog app is frontmost
        result = await self.get_frontmost_app()
        if not result.succeeded:
            return None

        frontmost = result.data.get("app", "")

        if any(app in frontmost for app in self.config.permission_dialog_apps):
            screenshot_path = await self._capture_screenshot("permission_dialog")
            return HumanCheckpoint.for_permission(
                f"macOS is requesting permission ({frontmost})",
                screenshot_path=screenshot_path,
            )

        return None

    async def _execute_with_logging(
        self,
        action_name: str,
        params: dict[str, Any],
        action_fn: Callable[[], Any],
    ) -> ActionResult:
        """
        Execute an action with logging and retry logic.

        Args:
            action_name: Name of the action for logging.
            params: Action parameters for logging.
            action_fn: Async function to execute.

        Returns:
            ActionResult from action or retry attempts.
        """
        screenshot_before = None
        if self.config.screenshot_all_actions:
            screenshot_before = await self._capture_screenshot(f"{action_name}_before")

        # Retry logic with exponential backoff
        last_result: ActionResult | None = None
        for attempt in range(self.config.max_retries):
            result = await action_fn()
            last_result = result

            # Success or human needed - don't retry
            if result.succeeded or result.needs_human:
                break

            # Timeout or failure - retry with backoff
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_base_delay_seconds * (2**attempt)
                await asyncio.sleep(delay)

        if not last_result:
            last_result = ActionResult.failure("No result from action")

        screenshot_after = None
        if self.config.screenshot_all_actions:
            screenshot_after = await self._capture_screenshot(f"{action_name}_after")

        # Log the action
        self._log_action(
            action_name,
            params,
            last_result,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

        return last_result

    def _log_action(
        self,
        action_name: str,
        params: dict[str, Any],
        result: ActionResult,
        screenshot_before: str | None = None,
        screenshot_after: str | None = None,
    ) -> None:
        """Add action to log."""
        self._action_counter += 1
        action_id = f"act_{self.session_id}_{self._action_counter:04d}"

        log_entry = ActionLog(
            action_id=action_id,
            module="macos",
            action=action_name,
            params=params,
            result=result,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

        self._action_log.append(log_entry)
