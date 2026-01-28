#!/usr/bin/env python3
"""
dialog_registry.py - Configurable Dialog Handler Registry

This module provides a YAML-configurable dialog handler registry for Unity Editor
automation. Dialog patterns can be defined in .claude-loop/dialog-handlers.yaml
with regex-based matching and configurable actions.

Usage:
    from agents.computer_use.dialog_registry import (
        DialogRegistry,
        DialogHandler,
        DialogAction,
        DialogMatchResult,
        load_dialog_registry,
    )

    # Load from YAML config
    registry = load_dialog_registry()

    # Or load from custom path
    registry = DialogRegistry.from_yaml("path/to/handlers.yaml")

    # Match and handle a dialog
    result = registry.match_dialog(window_title="Save Scene?", content="Save changes?")
    if result:
        action_result = registry.execute_action(result)
"""

import hashlib
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# YAML support - optional dependency
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False

# Screenshot capture - optional for capture_and_abort action
try:
    from .screenshot import capture_screenshot
    SCREENSHOT_AVAILABLE = True
except ImportError:
    capture_screenshot = None
    SCREENSHOT_AVAILABLE = False


# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DialogActionType(Enum):
    """Types of actions that can be taken when a dialog is matched."""
    CLICK_BUTTON = "click_button"
    CAPTURE_AND_ABORT = "capture_and_abort"
    REQUIRE_HUMAN = "require_human"
    IGNORE = "ignore"


class DialogMatchType(Enum):
    """How the dialog pattern should be matched."""
    TITLE = "title"
    CONTENT = "content"
    BOTH = "both"


@dataclass
class DialogHandler:
    """Configuration for handling a specific dialog type.

    Attributes:
        name: Human-readable identifier for this handler.
        pattern: Regex pattern or list of patterns to match.
        match_type: Whether to match title, content, or both.
        action: Action to take when dialog is matched.
        action_params: Parameters for the action (e.g., button name for click_button).
        priority: Lower numbers are matched first (default 100).
        enabled: Whether this handler is active.
        description: Human-readable description.
        wait_after: Seconds to wait after handling the dialog.
    """
    name: str
    pattern: Union[str, List[str]]
    match_type: DialogMatchType = DialogMatchType.TITLE
    action: DialogActionType = DialogActionType.CLICK_BUTTON
    action_params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    enabled: bool = True
    description: str = ""
    wait_after: float = 0.5

    # Compiled regex patterns (set during initialization)
    _compiled_patterns: List[re.Pattern] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Compile regex patterns after initialization."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile the pattern(s) into regex objects."""
        patterns = [self.pattern] if isinstance(self.pattern, str) else self.pattern
        self._compiled_patterns = []
        for p in patterns:
            try:
                # Use case-insensitive matching by default
                self._compiled_patterns.append(re.compile(p, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{p}' in handler '{self.name}': {e}")

    def matches(self, title: Optional[str] = None, content: Optional[str] = None) -> bool:
        """Check if this handler matches the given dialog.

        Args:
            title: The dialog window title.
            content: The dialog content/message.

        Returns:
            True if any pattern matches according to match_type.
        """
        if not self.enabled:
            return False

        texts_to_check = []
        if self.match_type == DialogMatchType.TITLE and title:
            texts_to_check = [title]
        elif self.match_type == DialogMatchType.CONTENT and content:
            texts_to_check = [content]
        elif self.match_type == DialogMatchType.BOTH:
            if title:
                texts_to_check.append(title)
            if content:
                texts_to_check.append(content)

        for text in texts_to_check:
            for pattern in self._compiled_patterns:
                if pattern.search(text):
                    return True
        return False


@dataclass
class DialogMatchResult:
    """Result of matching a dialog against the registry.

    Attributes:
        handler: The matched handler.
        matched_text: The text that triggered the match.
        matched_pattern: The pattern that matched.
        timestamp: When the match occurred.
    """
    handler: DialogHandler
    matched_text: str
    matched_pattern: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DialogActionResult:
    """Result of executing a dialog action.

    Attributes:
        success: Whether the action completed successfully.
        action_type: The type of action that was executed.
        handler_name: Name of the handler that triggered this action.
        message: Human-readable description of what happened.
        screenshot_path: Path to screenshot if capture_and_abort was used.
        requires_human: True if human intervention is required.
        timestamp: When the action was executed.
    """
    success: bool
    action_type: DialogActionType
    handler_name: str
    message: str
    screenshot_path: Optional[str] = None
    requires_human: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DialogLogEntry:
    """Log entry for a handled dialog.

    Attributes:
        timestamp: When the dialog was handled.
        handler_name: Name of the handler that matched.
        dialog_title: Title of the matched dialog.
        dialog_content: Content of the matched dialog (if available).
        action_type: Action that was taken.
        action_result: Result of the action.
        screenshot_path: Path to screenshot if one was taken.
    """
    timestamp: datetime
    handler_name: str
    dialog_title: Optional[str]
    dialog_content: Optional[str]
    action_type: DialogActionType
    action_result: DialogActionResult
    screenshot_path: Optional[str] = None


# =============================================================================
# Dialog Registry Class
# =============================================================================


class DialogRegistry:
    """Registry of dialog handlers loaded from YAML configuration.

    The registry loads dialog patterns from a YAML file and provides
    methods to match dialogs and execute appropriate actions.

    Example YAML configuration:
    ```yaml
    handlers:
      - name: save_scene
        pattern: "(save|unsaved).*scene"
        match_type: title
        action: click_button
        action_params:
          button: "Save"
        priority: 10
        description: Auto-save scene when prompted

      - name: api_update
        pattern:
          - "API.*update"
          - "deprecated.*API"
        match_type: both
        action: click_button
        action_params:
          button: "I Made a Backup. Go Ahead!"
        wait_after: 5.0

      - name: critical_error
        pattern: "(fatal|critical).*error"
        match_type: content
        action: capture_and_abort
        action_params:
          reason: "Critical error detected"

      - name: license_dialog
        pattern: "license"
        match_type: title
        action: require_human
        action_params:
          message: "License dialog requires manual handling"

      - name: telemetry
        pattern: "usage.*data|analytics"
        action: ignore
    ```
    """

    DEFAULT_CONFIG_PATH = ".claude-loop/dialog-handlers.yaml"

    def __init__(self, handlers: Optional[List[DialogHandler]] = None):
        """Initialize the dialog registry.

        Args:
            handlers: Optional list of DialogHandler instances.
        """
        self.handlers: List[DialogHandler] = handlers or []
        self._log: List[DialogLogEntry] = []
        self._button_click_callback: Optional[Callable[[str], bool]] = None
        self._screenshot_callback: Optional[Callable[[], bytes]] = None
        self._human_callback: Optional[Callable[[str], None]] = None

        # Sort handlers by priority on initialization
        self._sort_handlers()

    def _sort_handlers(self):
        """Sort handlers by priority (lower numbers first)."""
        self.handlers.sort(key=lambda h: h.priority)

    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> "DialogRegistry":
        """Load dialog registry from a YAML file.

        Args:
            yaml_path: Path to the YAML configuration file.

        Returns:
            DialogRegistry instance with loaded handlers.

        Raises:
            ImportError: If PyYAML is not installed.
            FileNotFoundError: If the YAML file doesn't exist.
            ValueError: If the YAML is invalid.
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required for YAML configuration. "
                "Install with: pip install pyyaml"
            )

        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Dialog handlers config not found: {yaml_path}")

        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)  # type: ignore[union-attr]

        if not config or 'handlers' not in config:
            return cls(handlers=[])

        handlers = []
        for handler_config in config.get('handlers', []):
            try:
                handler = cls._parse_handler_config(handler_config)
                handlers.append(handler)
            except Exception as e:
                logger.warning(f"Skipping invalid handler config: {e}")

        return cls(handlers=handlers)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "DialogRegistry":
        """Load dialog registry from a dictionary configuration.

        Args:
            config: Dictionary with 'handlers' key containing handler configs.

        Returns:
            DialogRegistry instance with loaded handlers.
        """
        handlers = []
        for handler_config in config.get('handlers', []):
            try:
                handler = cls._parse_handler_config(handler_config)
                handlers.append(handler)
            except Exception as e:
                logger.warning(f"Skipping invalid handler config: {e}")

        return cls(handlers=handlers)

    @staticmethod
    def _parse_handler_config(config: Dict[str, Any]) -> DialogHandler:
        """Parse a handler configuration dictionary into a DialogHandler.

        Args:
            config: Dictionary with handler configuration.

        Returns:
            DialogHandler instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if 'name' not in config:
            raise ValueError("Handler config must have 'name' field")
        if 'pattern' not in config:
            raise ValueError("Handler config must have 'pattern' field")

        # Parse match_type
        match_type_str = config.get('match_type', 'title')
        try:
            match_type = DialogMatchType(match_type_str)
        except ValueError:
            logger.warning(f"Invalid match_type '{match_type_str}', using 'title'")
            match_type = DialogMatchType.TITLE

        # Parse action
        action_str = config.get('action', 'click_button')
        try:
            action = DialogActionType(action_str)
        except ValueError:
            logger.warning(f"Invalid action '{action_str}', using 'click_button'")
            action = DialogActionType.CLICK_BUTTON

        return DialogHandler(
            name=config['name'],
            pattern=config['pattern'],
            match_type=match_type,
            action=action,
            action_params=config.get('action_params', {}),
            priority=config.get('priority', 100),
            enabled=config.get('enabled', True),
            description=config.get('description', ''),
            wait_after=config.get('wait_after', 0.5),
        )

    def add_handler(self, handler: DialogHandler):
        """Add a handler to the registry.

        Args:
            handler: DialogHandler instance to add.
        """
        self.handlers.append(handler)
        self._sort_handlers()

    def remove_handler(self, name: str) -> bool:
        """Remove a handler by name.

        Args:
            name: Name of the handler to remove.

        Returns:
            True if a handler was removed, False otherwise.
        """
        original_count = len(self.handlers)
        self.handlers = [h for h in self.handlers if h.name != name]
        return len(self.handlers) < original_count

    def get_handler(self, name: str) -> Optional[DialogHandler]:
        """Get a handler by name.

        Args:
            name: Name of the handler to retrieve.

        Returns:
            DialogHandler if found, None otherwise.
        """
        for handler in self.handlers:
            if handler.name == name:
                return handler
        return None

    def match_dialog(
        self,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> Optional[DialogMatchResult]:
        """Match a dialog against registered handlers.

        Handlers are checked in priority order (lower numbers first).
        The first matching handler is returned.

        Args:
            title: The dialog window title.
            content: The dialog content/message.

        Returns:
            DialogMatchResult if a match is found, None otherwise.
        """
        for handler in self.handlers:
            if handler.matches(title=title, content=content):
                # Determine which text and pattern matched
                matched_text = ""
                matched_pattern = ""

                texts_to_check = []
                if handler.match_type in (DialogMatchType.TITLE, DialogMatchType.BOTH) and title:
                    texts_to_check.append(title)
                if handler.match_type in (DialogMatchType.CONTENT, DialogMatchType.BOTH) and content:
                    texts_to_check.append(content)

                for text in texts_to_check:
                    for pattern in handler._compiled_patterns:
                        match = pattern.search(text)
                        if match:
                            matched_text = text
                            matched_pattern = pattern.pattern
                            break
                    if matched_text:
                        break

                logger.info(
                    f"Dialog matched handler '{handler.name}': "
                    f"'{matched_text[:50]}...' matched pattern '{matched_pattern}'"
                )

                return DialogMatchResult(
                    handler=handler,
                    matched_text=matched_text,
                    matched_pattern=matched_pattern,
                )

        return None

    def set_button_click_callback(self, callback: Callable[[str], bool]):
        """Set the callback function for clicking buttons.

        Args:
            callback: Function that takes button name and returns success.
        """
        self._button_click_callback = callback

    def set_screenshot_callback(self, callback: Callable[[], bytes]):
        """Set the callback function for taking screenshots.

        Args:
            callback: Function that returns screenshot bytes.
        """
        self._screenshot_callback = callback

    def set_human_callback(self, callback: Callable[[str], None]):
        """Set the callback function for human intervention notifications.

        Args:
            callback: Function that takes a message and notifies a human.
        """
        self._human_callback = callback

    def execute_action(
        self,
        match_result: DialogMatchResult,
        dialog_title: Optional[str] = None,
        dialog_content: Optional[str] = None,
    ) -> DialogActionResult:
        """Execute the action for a matched dialog.

        Args:
            match_result: Result from match_dialog().
            dialog_title: Original dialog title (for logging).
            dialog_content: Original dialog content (for logging).

        Returns:
            DialogActionResult with details of what happened.
        """
        handler = match_result.handler
        action = handler.action
        params = handler.action_params

        result: DialogActionResult

        if action == DialogActionType.CLICK_BUTTON:
            result = self._execute_click_button(handler, params)
        elif action == DialogActionType.CAPTURE_AND_ABORT:
            result = self._execute_capture_and_abort(handler, params)
        elif action == DialogActionType.REQUIRE_HUMAN:
            result = self._execute_require_human(handler, params)
        elif action == DialogActionType.IGNORE:
            result = self._execute_ignore(handler, params)
        else:
            result = DialogActionResult(
                success=False,
                action_type=action,
                handler_name=handler.name,
                message=f"Unknown action type: {action}",
            )

        # Log the handled dialog
        log_entry = DialogLogEntry(
            timestamp=datetime.now(),
            handler_name=handler.name,
            dialog_title=dialog_title,
            dialog_content=dialog_content,
            action_type=action,
            action_result=result,
            screenshot_path=result.screenshot_path,
        )
        self._log.append(log_entry)

        logger.info(
            f"Dialog handled: handler='{handler.name}' action={action.value} "
            f"success={result.success} message='{result.message}'"
        )

        # Wait after handling if configured
        if result.success and handler.wait_after > 0:
            time.sleep(handler.wait_after)

        return result

    def _execute_click_button(
        self,
        handler: DialogHandler,
        params: Dict[str, Any]
    ) -> DialogActionResult:
        """Execute click_button action.

        Args:
            handler: The dialog handler.
            params: Action parameters (expects 'button' key).

        Returns:
            DialogActionResult.
        """
        button_name = params.get('button', 'OK')
        buttons_to_try = params.get('buttons', [button_name])
        if isinstance(buttons_to_try, str):
            buttons_to_try = [buttons_to_try]

        if not self._button_click_callback:
            # Use AppleScript as fallback
            success = self._applescript_click_button(buttons_to_try)
        else:
            success = False
            for btn in buttons_to_try:
                if self._button_click_callback(btn):
                    success = True
                    button_name = btn
                    break

        return DialogActionResult(
            success=success,
            action_type=DialogActionType.CLICK_BUTTON,
            handler_name=handler.name,
            message=f"Clicked button '{button_name}'" if success else f"Failed to click button '{button_name}'",
        )

    def _applescript_click_button(self, buttons: List[str]) -> bool:
        """Click a button using AppleScript.

        Args:
            buttons: List of button names to try (in order).

        Returns:
            True if a button was clicked successfully.
        """
        for button in buttons:
            script = f'''
            tell application "System Events"
                tell process "Unity"
                    try
                        click button "{button}" of front window
                        return "success"
                    end try
                end tell
            end tell
            return "failed"
            '''
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=5.0
                )
                if "success" in result.stdout:
                    return True
            except Exception as e:
                logger.debug(f"AppleScript click failed for '{button}': {e}")

        return False

    def _execute_capture_and_abort(
        self,
        handler: DialogHandler,
        params: Dict[str, Any]
    ) -> DialogActionResult:
        """Execute capture_and_abort action.

        Takes a screenshot and aborts the current operation.

        Args:
            handler: The dialog handler.
            params: Action parameters.

        Returns:
            DialogActionResult.
        """
        reason = params.get('reason', 'Dialog triggered abort')
        screenshot_path = None

        # Take screenshot
        screenshot_bytes: Optional[bytes] = None
        try:
            if self._screenshot_callback:
                screenshot_bytes = self._screenshot_callback()
            elif SCREENSHOT_AVAILABLE and capture_screenshot:
                # capture_screenshot() returns bytes directly
                screenshot_bytes = capture_screenshot()

            if screenshot_bytes:
                # Save screenshot to .claude-loop/screenshots/
                screenshot_dir = Path(".claude-loop/screenshots")
                screenshot_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_hash = hashlib.md5(screenshot_bytes).hexdigest()[:8]
                screenshot_path = str(screenshot_dir / f"abort_{handler.name}_{timestamp}_{screenshot_hash}.png")

                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_bytes)

                logger.info(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")

        return DialogActionResult(
            success=True,
            action_type=DialogActionType.CAPTURE_AND_ABORT,
            handler_name=handler.name,
            message=f"Captured screenshot and aborted: {reason}",
            screenshot_path=screenshot_path,
        )

    def _execute_require_human(
        self,
        handler: DialogHandler,
        params: Dict[str, Any]
    ) -> DialogActionResult:
        """Execute require_human action.

        Notifies that human intervention is required.

        Args:
            handler: The dialog handler.
            params: Action parameters.

        Returns:
            DialogActionResult.
        """
        message = params.get('message', 'Human intervention required')

        if self._human_callback:
            try:
                self._human_callback(message)
            except Exception as e:
                logger.warning(f"Human callback failed: {e}")

        logger.warning(f"HUMAN REQUIRED: {handler.name} - {message}")

        return DialogActionResult(
            success=True,
            action_type=DialogActionType.REQUIRE_HUMAN,
            handler_name=handler.name,
            message=message,
            requires_human=True,
        )

    def _execute_ignore(
        self,
        handler: DialogHandler,
        params: Dict[str, Any]
    ) -> DialogActionResult:
        """Execute ignore action.

        Simply logs that the dialog was ignored.

        Args:
            handler: The dialog handler.
            params: Action parameters.

        Returns:
            DialogActionResult.
        """
        reason = params.get('reason', 'Dialog intentionally ignored')

        return DialogActionResult(
            success=True,
            action_type=DialogActionType.IGNORE,
            handler_name=handler.name,
            message=reason,
        )

    def get_log(self) -> List[DialogLogEntry]:
        """Get the log of all handled dialogs.

        Returns:
            List of DialogLogEntry objects.
        """
        return self._log.copy()

    def clear_log(self):
        """Clear the dialog handling log."""
        self._log.clear()

    def get_log_summary(self) -> Dict[str, Any]:
        """Get a summary of dialog handling activity.

        Returns:
            Dictionary with summary statistics.
        """
        summary = {
            'total_handled': len(self._log),
            'by_handler': {},
            'by_action': {},
            'successful': 0,
            'failed': 0,
            'requiring_human': 0,
        }

        for entry in self._log:
            # By handler
            handler_name = entry.handler_name
            if handler_name not in summary['by_handler']:
                summary['by_handler'][handler_name] = 0
            summary['by_handler'][handler_name] += 1

            # By action type
            action = entry.action_type.value
            if action not in summary['by_action']:
                summary['by_action'][action] = 0
            summary['by_action'][action] += 1

            # Success/failure
            if entry.action_result.success:
                summary['successful'] += 1
            else:
                summary['failed'] += 1

            # Human required
            if entry.action_result.requires_human:
                summary['requiring_human'] += 1

        return summary

    def to_yaml(self, output_path: Union[str, Path]):
        """Save the current registry to a YAML file.

        Args:
            output_path: Path to write the YAML file.

        Raises:
            ImportError: If PyYAML is not installed.
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required for YAML export. "
                "Install with: pip install pyyaml"
            )

        config = {'handlers': []}
        for handler in self.handlers:
            handler_config = {
                'name': handler.name,
                'pattern': handler.pattern,
                'match_type': handler.match_type.value,
                'action': handler.action.value,
                'priority': handler.priority,
                'enabled': handler.enabled,
            }
            if handler.action_params:
                handler_config['action_params'] = handler.action_params
            if handler.description:
                handler_config['description'] = handler.description
            if handler.wait_after != 0.5:
                handler_config['wait_after'] = handler.wait_after

            config['handlers'].append(handler_config)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)  # type: ignore[union-attr]

    def __len__(self) -> int:
        """Return the number of handlers in the registry."""
        return len(self.handlers)

    def __repr__(self) -> str:
        return f"DialogRegistry(handlers={len(self.handlers)}, log_entries={len(self._log)})"


# =============================================================================
# Convenience Functions
# =============================================================================


def load_dialog_registry(
    config_path: Optional[Union[str, Path]] = None
) -> DialogRegistry:
    """Load dialog registry from the default or specified YAML config.

    Args:
        config_path: Optional path to YAML config. Defaults to
                     .claude-loop/dialog-handlers.yaml

    Returns:
        DialogRegistry instance. Returns empty registry if config not found.
    """
    if config_path is None:
        config_path = Path(DialogRegistry.DEFAULT_CONFIG_PATH)
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.info(f"Dialog handlers config not found at {config_path}, using empty registry")
        return DialogRegistry()

    try:
        return DialogRegistry.from_yaml(config_path)
    except Exception as e:
        logger.warning(f"Failed to load dialog handlers config: {e}")
        return DialogRegistry()


def create_default_config(output_path: Optional[Union[str, Path]] = None):
    """Create a default dialog handlers YAML configuration file.

    Args:
        output_path: Path to write the config. Defaults to
                     .claude-loop/dialog-handlers.yaml
    """
    if output_path is None:
        output_path = Path(DialogRegistry.DEFAULT_CONFIG_PATH)
    else:
        output_path = Path(output_path)

    default_config = {
        'handlers': [
            {
                'name': 'save_scene',
                'pattern': '(save|unsaved).*scene',
                'match_type': 'title',
                'action': 'click_button',
                'action_params': {'button': 'Save', 'buttons': ['Save', 'Yes', 'OK']},
                'priority': 10,
                'description': 'Auto-save scene when prompted',
                'wait_after': 1.0,
            },
            {
                'name': 'api_update',
                'pattern': ['API.*update', 'deprecated.*API', 'Update.*API'],
                'match_type': 'both',
                'action': 'click_button',
                'action_params': {'button': 'I Made a Backup. Go Ahead!'},
                'priority': 20,
                'description': 'Accept API updates after Unity upgrade',
                'wait_after': 5.0,
            },
            {
                'name': 'restart_required',
                'pattern': ['restart.*editor', 'editor.*restart', 'restart.*required'],
                'match_type': 'both',
                'action': 'click_button',
                'action_params': {'buttons': ['Restart', 'Yes', 'OK']},
                'priority': 30,
                'description': 'Accept editor restart prompts',
                'wait_after': 5.0,
            },
            {
                'name': 'input_system',
                'pattern': ['input.*system', 'new.*input.*backend'],
                'match_type': 'both',
                'action': 'click_button',
                'action_params': {'button': 'Yes'},
                'priority': 40,
                'description': 'Enable new input system when prompted',
                'wait_after': 2.0,
            },
            {
                'name': 'import_package',
                'pattern': 'import.*package',
                'match_type': 'title',
                'action': 'click_button',
                'action_params': {'buttons': ['Import', 'Import All', 'OK']},
                'priority': 50,
                'description': 'Auto-accept package imports',
                'wait_after': 2.0,
            },
            {
                'name': 'build_failed',
                'pattern': ['build.*fail', 'compilation.*error', 'build.*error'],
                'match_type': 'both',
                'action': 'capture_and_abort',
                'action_params': {'reason': 'Build failed - capturing state'},
                'priority': 5,
                'description': 'Capture screenshot on build failure',
            },
            {
                'name': 'safe_mode',
                'pattern': 'safe.*mode',
                'match_type': 'title',
                'action': 'require_human',
                'action_params': {'message': 'Safe mode dialog requires manual decision'},
                'priority': 1,
                'description': 'Safe mode requires human decision',
            },
            {
                'name': 'license_expired',
                'pattern': ['license.*expir', 'subscription', 'activate.*license'],
                'match_type': 'both',
                'action': 'require_human',
                'action_params': {'message': 'License issue requires manual resolution'},
                'priority': 1,
                'description': 'License dialogs require human handling',
            },
            {
                'name': 'telemetry',
                'pattern': ['usage.*data', 'analytics', 'telemetry', 'privacy'],
                'match_type': 'both',
                'action': 'ignore',
                'action_params': {'reason': 'Telemetry dialog ignored'},
                'priority': 100,
                'description': 'Ignore telemetry/analytics prompts',
            },
        ]
    }

    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required to create config. "
            "Install with: pip install pyyaml"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)  # type: ignore[union-attr]

    logger.info(f"Created default dialog handlers config at {output_path}")


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Main class
    "DialogRegistry",
    # Enums
    "DialogActionType",
    "DialogMatchType",
    # Data classes
    "DialogHandler",
    "DialogMatchResult",
    "DialogActionResult",
    "DialogLogEntry",
    # Convenience functions
    "load_dialog_registry",
    "create_default_config",
    # Availability flags
    "YAML_AVAILABLE",
]
