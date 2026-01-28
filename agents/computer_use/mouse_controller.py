#!/usr/bin/env python3
"""
mouse_controller.py - Coordinate-based mouse control for macOS

This module provides mouse control capabilities using macOS Quartz framework.
It supports clicks at specific screen coordinates across multiple displays,
with automatic coordinate translation for multi-monitor setups.

Usage:
    from agents.computer_use.mouse_controller import MouseController

    controller = MouseController()
    controller.click_at(100, 200)
    controller.double_click_at(100, 200)
    controller.right_click_at(100, 200)
    controller.drag_from_to(100, 200, 300, 400)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)

# Platform-specific imports with fallbacks
try:
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventPost,
        CGEventSetType,
        CGEventGetLocation,
        CGEventCreate,
        kCGEventMouseMoved,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged,
        kCGEventRightMouseDown,
        kCGEventRightMouseUp,
        kCGEventOtherMouseDown,
        kCGEventOtherMouseUp,
        kCGMouseButtonLeft,
        kCGMouseButtonRight,
        kCGMouseButtonCenter,
        kCGHIDEventTap,
    )
    from Quartz.CoreGraphics import (
        CGWarpMouseCursorPosition,
        CGPoint,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False
    # Define dummy types for type hints when Quartz not available
    CGPoint = None  # type: ignore


class MouseButton(Enum):
    """Mouse button types."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class ClickType(Enum):
    """Types of click actions."""
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass
class ClickResult:
    """Result of a click operation."""
    success: bool
    x: float
    y: float
    click_type: ClickType
    timestamp: datetime = field(default_factory=datetime.now)
    actual_x: Optional[float] = None  # Actual position after click (if verified)
    actual_y: Optional[float] = None
    verified: bool = False
    error: Optional[str] = None
    display_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "success": self.success,
            "x": self.x,
            "y": self.y,
            "click_type": self.click_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actual_x": self.actual_x,
            "actual_y": self.actual_y,
            "verified": self.verified,
            "error": self.error,
            "display_id": self.display_id,
        }


@dataclass
class DragResult:
    """Result of a drag operation."""
    success: bool
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    timestamp: datetime = field(default_factory=datetime.now)
    actual_end_x: Optional[float] = None
    actual_end_y: Optional[float] = None
    verified: bool = False
    error: Optional[str] = None
    steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "success": self.success,
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "timestamp": self.timestamp.isoformat(),
            "actual_end_x": self.actual_end_x,
            "actual_end_y": self.actual_end_y,
            "verified": self.verified,
            "error": self.error,
            "steps": self.steps,
        }


@dataclass
class ClickLogEntry:
    """Entry in the click log for debugging."""
    timestamp: datetime
    action: str
    x: float
    y: float
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


class MouseController:
    """
    Controls mouse actions on macOS using Quartz framework.

    This class provides:
    - Single, double, and triple click at coordinates
    - Right-click and middle-click
    - Mouse drag operations
    - Multi-display coordinate support
    - Click verification
    - Action logging for debugging

    Example:
        controller = MouseController()

        # Simple click
        controller.click_at(100, 200)

        # Double-click
        controller.double_click_at(300, 400)

        # Right-click for context menu
        controller.right_click_at(500, 600)

        # Drag from one point to another
        controller.drag_from_to(100, 100, 200, 200)
    """

    # Default delay between mouse events (seconds)
    DEFAULT_CLICK_DELAY = 0.01
    DEFAULT_DOUBLE_CLICK_INTERVAL = 0.1
    DEFAULT_DRAG_STEP_DELAY = 0.005

    def __init__(
        self,
        click_delay: float = DEFAULT_CLICK_DELAY,
        double_click_interval: float = DEFAULT_DOUBLE_CLICK_INTERVAL,
        enable_logging: bool = True,
        log_file: Optional[Path] = None,
    ):
        """
        Initialize the mouse controller.

        Args:
            click_delay: Delay between mouse down and up events.
            double_click_interval: Interval between clicks for double/triple click.
            enable_logging: If True, log all mouse actions.
            log_file: Path to save action logs. If None, logs to default location.
        """
        if not QUARTZ_AVAILABLE:
            raise RuntimeError(
                "Quartz framework not available. This module requires macOS with "
                "pyobjc-framework-Quartz installed. Install with: "
                "pip install pyobjc-framework-Quartz"
            )

        self._click_delay = click_delay
        self._double_click_interval = double_click_interval
        self._enable_logging = enable_logging
        self._log_file = log_file or Path(".claude-loop/logs/mouse_actions.log")
        self._click_log: List[ClickLogEntry] = []

        # Import screenshot module for coordinate translation (optional)
        self._screenshot_module = None
        try:
            from . import screenshot
            self._screenshot_module = screenshot
        except ImportError:
            logger.warning("Screenshot module not available. Coordinate translation limited.")

    def _log_action(
        self,
        action: str,
        x: float,
        y: float,
        success: bool,
        **details: Any
    ) -> None:
        """Log a mouse action for debugging."""
        if not self._enable_logging:
            return

        entry = ClickLogEntry(
            timestamp=datetime.now(),
            action=action,
            x=x,
            y=y,
            success=success,
            details=details,
        )
        self._click_log.append(entry)

        # Log to logger
        log_msg = f"Mouse {action} at ({x:.1f}, {y:.1f}) - {'success' if success else 'failed'}"
        if details:
            log_msg += f" - {details}"
        if success:
            logger.debug(log_msg)
        else:
            logger.warning(log_msg)

    def get_current_position(self) -> Tuple[float, float]:
        """
        Get the current mouse cursor position.

        Returns:
            Tuple of (x, y) coordinates in global screen space.
        """
        event = CGEventCreate(None)
        if event is None:
            raise RuntimeError("Failed to create event for position query")

        location = CGEventGetLocation(event)
        return (location.x, location.y)

    def move_to(self, x: float, y: float) -> bool:
        """
        Move the mouse cursor to the specified coordinates.

        Args:
            x: X coordinate in global screen space (can be negative for left displays).
            y: Y coordinate in global screen space (can be negative for above displays).

        Returns:
            True if successful.
        """
        try:
            point = CGPoint(x, y)
            CGWarpMouseCursorPosition(point)
            self._log_action("move", x, y, True)
            return True
        except Exception as e:
            self._log_action("move", x, y, False, error=str(e))
            return False

    def click_at(
        self,
        x: float,
        y: float,
        verify: bool = False
    ) -> ClickResult:
        """
        Perform a left-click at the specified coordinates.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            verify: If True, verify the click landed at the correct position.

        Returns:
            ClickResult with details of the operation.
        """
        return self._perform_click(x, y, ClickType.SINGLE, verify=verify)

    def double_click_at(
        self,
        x: float,
        y: float,
        verify: bool = False
    ) -> ClickResult:
        """
        Perform a double-click at the specified coordinates.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            verify: If True, verify the click landed at the correct position.

        Returns:
            ClickResult with details of the operation.
        """
        return self._perform_click(x, y, ClickType.DOUBLE, verify=verify)

    def triple_click_at(
        self,
        x: float,
        y: float,
        verify: bool = False
    ) -> ClickResult:
        """
        Perform a triple-click at the specified coordinates.
        Useful for selecting entire lines or paragraphs.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            verify: If True, verify the click landed at the correct position.

        Returns:
            ClickResult with details of the operation.
        """
        return self._perform_click(x, y, ClickType.TRIPLE, verify=verify)

    def right_click_at(
        self,
        x: float,
        y: float,
        verify: bool = False
    ) -> ClickResult:
        """
        Perform a right-click (context menu) at the specified coordinates.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            verify: If True, verify the click landed at the correct position.

        Returns:
            ClickResult with details of the operation.
        """
        return self._perform_click(x, y, ClickType.RIGHT, verify=verify)

    def middle_click_at(
        self,
        x: float,
        y: float,
        verify: bool = False
    ) -> ClickResult:
        """
        Perform a middle-click at the specified coordinates.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            verify: If True, verify the click landed at the correct position.

        Returns:
            ClickResult with details of the operation.
        """
        return self._perform_click(x, y, ClickType.MIDDLE, verify=verify)

    def _perform_click(
        self,
        x: float,
        y: float,
        click_type: ClickType,
        verify: bool = False
    ) -> ClickResult:
        """
        Internal method to perform a click of any type.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.
            click_type: Type of click to perform.
            verify: If True, verify the click position.

        Returns:
            ClickResult with details of the operation.
        """
        try:
            point = CGPoint(x, y)

            # Get display ID for logging (if screenshot module available)
            display_id = None
            if self._screenshot_module:
                try:
                    result = self._screenshot_module.coordinate_to_display(x, y)
                    if result:
                        display_id = result[0].display_id
                except Exception:
                    pass

            # Move mouse to position first
            CGWarpMouseCursorPosition(point)
            time.sleep(self._click_delay)

            # Determine number of clicks and button type
            if click_type == ClickType.RIGHT:
                self._post_right_click(point)
            elif click_type == ClickType.MIDDLE:
                self._post_middle_click(point)
            else:
                # Single, double, or triple left click
                click_count = {
                    ClickType.SINGLE: 1,
                    ClickType.DOUBLE: 2,
                    ClickType.TRIPLE: 3,
                }.get(click_type, 1)
                self._post_left_clicks(point, click_count)

            # Verify position if requested
            actual_x, actual_y = None, None
            verified = False
            if verify:
                time.sleep(self._click_delay)
                actual_x, actual_y = self.get_current_position()
                # Consider verified if within 2 pixels
                verified = abs(actual_x - x) <= 2 and abs(actual_y - y) <= 2

            result = ClickResult(
                success=True,
                x=x,
                y=y,
                click_type=click_type,
                actual_x=actual_x,
                actual_y=actual_y,
                verified=verified,
                display_id=display_id,
            )

            self._log_action(
                f"{click_type.value}_click",
                x, y, True,
                display_id=display_id,
                verified=verified
            )

            return result

        except Exception as e:
            error_msg = str(e)
            self._log_action(f"{click_type.value}_click", x, y, False, error=error_msg)
            return ClickResult(
                success=False,
                x=x,
                y=y,
                click_type=click_type,
                error=error_msg,
            )

    def _post_left_clicks(self, point: Any, count: int) -> None:
        """Post left mouse click events."""
        for i in range(count):
            # Mouse down
            event = CGEventCreateMouseEvent(
                None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, event)
            time.sleep(self._click_delay)

            # Mouse up
            event = CGEventCreateMouseEvent(
                None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, event)

            # Delay between clicks (not after last one)
            if i < count - 1:
                time.sleep(self._double_click_interval)

    def _post_right_click(self, point: Any) -> None:
        """Post right mouse click events."""
        # Mouse down
        event = CGEventCreateMouseEvent(
            None, kCGEventRightMouseDown, point, kCGMouseButtonRight
        )
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(self._click_delay)

        # Mouse up
        event = CGEventCreateMouseEvent(
            None, kCGEventRightMouseUp, point, kCGMouseButtonRight
        )
        CGEventPost(kCGHIDEventTap, event)

    def _post_middle_click(self, point: Any) -> None:
        """Post middle mouse click events."""
        # Mouse down
        event = CGEventCreateMouseEvent(
            None, kCGEventOtherMouseDown, point, kCGMouseButtonCenter
        )
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(self._click_delay)

        # Mouse up
        event = CGEventCreateMouseEvent(
            None, kCGEventOtherMouseUp, point, kCGMouseButtonCenter
        )
        CGEventPost(kCGHIDEventTap, event)

    def drag_from_to(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        duration: float = 0.5,
        steps: int = 20,
        verify: bool = False
    ) -> DragResult:
        """
        Perform a mouse drag from one point to another.

        Args:
            start_x: Starting X coordinate.
            start_y: Starting Y coordinate.
            end_x: Ending X coordinate.
            end_y: Ending Y coordinate.
            duration: Total duration of the drag in seconds.
            steps: Number of intermediate steps for smooth dragging.
            verify: If True, verify the final mouse position.

        Returns:
            DragResult with details of the operation.
        """
        try:
            # Move to start position
            start_point = CGPoint(start_x, start_y)
            CGWarpMouseCursorPosition(start_point)
            time.sleep(self._click_delay)

            # Mouse down at start
            event = CGEventCreateMouseEvent(
                None, kCGEventLeftMouseDown, start_point, kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, event)

            # Calculate step delays
            step_delay = duration / steps if steps > 0 else self.DEFAULT_DRAG_STEP_DELAY

            # Interpolate points and drag
            for i in range(1, steps + 1):
                t = i / steps
                current_x = start_x + (end_x - start_x) * t
                current_y = start_y + (end_y - start_y) * t
                current_point = CGPoint(current_x, current_y)

                # Post drag event
                event = CGEventCreateMouseEvent(
                    None, kCGEventLeftMouseDragged, current_point, kCGMouseButtonLeft
                )
                CGEventPost(kCGHIDEventTap, event)
                time.sleep(step_delay)

            # Mouse up at end
            end_point = CGPoint(end_x, end_y)
            event = CGEventCreateMouseEvent(
                None, kCGEventLeftMouseUp, end_point, kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, event)

            # Verify position if requested
            actual_end_x, actual_end_y = None, None
            verified = False
            if verify:
                time.sleep(self._click_delay)
                actual_end_x, actual_end_y = self.get_current_position()
                verified = abs(actual_end_x - end_x) <= 2 and abs(actual_end_y - end_y) <= 2

            result = DragResult(
                success=True,
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                actual_end_x=actual_end_x,
                actual_end_y=actual_end_y,
                verified=verified,
                steps=steps,
            )

            self._log_action(
                "drag",
                start_x, start_y, True,
                end_x=end_x, end_y=end_y,
                steps=steps, verified=verified
            )

            return result

        except Exception as e:
            error_msg = str(e)
            self._log_action(
                "drag",
                start_x, start_y, False,
                end_x=end_x, end_y=end_y,
                error=error_msg
            )
            return DragResult(
                success=False,
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                error=error_msg,
            )

    def translate_coordinates(
        self,
        x: float,
        y: float,
        from_display: Optional[int] = None,
        to_display: Optional[int] = None
    ) -> Tuple[float, float]:
        """
        Translate coordinates between display coordinate spaces.

        Supports multi-display setups including:
        - Displays to the left (negative X coordinates)
        - Displays above (negative Y coordinates)
        - Different scale factors (Retina vs non-Retina)

        Args:
            x: X coordinate in the source coordinate space.
            y: Y coordinate in the source coordinate space.
            from_display: Source display ID. If None, assumed to be local to that display.
            to_display: Target display ID. If None, returns global coordinates.

        Returns:
            Tuple of (translated_x, translated_y) in the target coordinate space.

        Note:
            Global coordinates on macOS:
            - Primary display origin is (0, 0) at top-left
            - Displays to the left have negative X
            - Displays above have negative Y
        """
        if self._screenshot_module is None:
            # No translation available - return as-is
            logger.warning("Screenshot module not available for coordinate translation")
            return (x, y)

        try:
            # If converting from local to global
            if from_display is not None and to_display is None:
                result = self._screenshot_module.display_to_global(from_display, x, y)
                if result:
                    return result
                logger.warning(f"Display {from_display} not found for coordinate translation")
                return (x, y)

            # If converting from global to local
            if from_display is None and to_display is not None:
                capture = self._screenshot_module.MultiMonitorCapture()
                displays = capture.get_displays()
                for display in displays:
                    if display.display_id == to_display:
                        return display.bounds.to_local(x, y)
                logger.warning(f"Display {to_display} not found for coordinate translation")
                return (x, y)

            # If converting between displays
            if from_display is not None and to_display is not None:
                # First convert to global, then to local
                global_coords = self._screenshot_module.display_to_global(from_display, x, y)
                if global_coords is None:
                    logger.warning(f"Display {from_display} not found")
                    return (x, y)

                capture = self._screenshot_module.MultiMonitorCapture()
                displays = capture.get_displays()
                for display in displays:
                    if display.display_id == to_display:
                        return display.bounds.to_local(global_coords[0], global_coords[1])

                logger.warning(f"Display {to_display} not found")
                return global_coords

            # No translation needed
            return (x, y)

        except Exception as e:
            logger.warning(f"Coordinate translation failed: {e}")
            return (x, y)

    def get_display_at_point(self, x: float, y: float) -> Optional[int]:
        """
        Get the display ID containing the specified point.

        Args:
            x: X coordinate in global screen space.
            y: Y coordinate in global screen space.

        Returns:
            Display ID if found, None otherwise.
        """
        if self._screenshot_module is None:
            return None

        try:
            result = self._screenshot_module.coordinate_to_display(x, y)
            if result:
                return result[0].display_id
            return None
        except Exception:
            return None

    def get_action_log(self) -> List[Dict[str, Any]]:
        """
        Get the log of all mouse actions.

        Returns:
            List of action log entries as dictionaries.
        """
        return [
            {
                "timestamp": entry.timestamp.isoformat(),
                "action": entry.action,
                "x": entry.x,
                "y": entry.y,
                "success": entry.success,
                **entry.details,
            }
            for entry in self._click_log
        ]

    def clear_action_log(self) -> None:
        """Clear the action log."""
        self._click_log.clear()

    def save_action_log(self, path: Optional[Path] = None) -> Path:
        """
        Save the action log to a file.

        Args:
            path: Path to save the log. If None, uses default location.

        Returns:
            Path where the log was saved.
        """
        import json

        path = path or self._log_file
        path.parent.mkdir(parents=True, exist_ok=True)

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "actions": self.get_action_log(),
        }

        with open(path, "w") as f:
            json.dump(log_data, f, indent=2)

        return path


# Convenience functions for simple usage

def click_at(x: float, y: float, verify: bool = False) -> ClickResult:
    """
    Perform a left-click at the specified coordinates.

    Args:
        x: X coordinate in global screen space.
        y: Y coordinate in global screen space.
        verify: If True, verify the click position.

    Returns:
        ClickResult with details of the operation.
    """
    controller = MouseController(enable_logging=False)
    return controller.click_at(x, y, verify=verify)


def double_click_at(x: float, y: float, verify: bool = False) -> ClickResult:
    """
    Perform a double-click at the specified coordinates.

    Args:
        x: X coordinate in global screen space.
        y: Y coordinate in global screen space.
        verify: If True, verify the click position.

    Returns:
        ClickResult with details of the operation.
    """
    controller = MouseController(enable_logging=False)
    return controller.double_click_at(x, y, verify=verify)


def right_click_at(x: float, y: float, verify: bool = False) -> ClickResult:
    """
    Perform a right-click at the specified coordinates.

    Args:
        x: X coordinate in global screen space.
        y: Y coordinate in global screen space.
        verify: If True, verify the click position.

    Returns:
        ClickResult with details of the operation.
    """
    controller = MouseController(enable_logging=False)
    return controller.right_click_at(x, y, verify=verify)


def drag_from_to(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    duration: float = 0.5,
    verify: bool = False
) -> DragResult:
    """
    Perform a mouse drag from one point to another.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        duration: Total duration of the drag in seconds.
        verify: If True, verify the final mouse position.

    Returns:
        DragResult with details of the operation.
    """
    controller = MouseController(enable_logging=False)
    return controller.drag_from_to(start_x, start_y, end_x, end_y, duration=duration, verify=verify)


def get_mouse_position() -> Tuple[float, float]:
    """
    Get the current mouse cursor position.

    Returns:
        Tuple of (x, y) coordinates in global screen space.
    """
    controller = MouseController(enable_logging=False)
    return controller.get_current_position()


def move_mouse_to(x: float, y: float) -> bool:
    """
    Move the mouse cursor to the specified coordinates.

    Args:
        x: X coordinate in global screen space.
        y: Y coordinate in global screen space.

    Returns:
        True if successful.
    """
    controller = MouseController(enable_logging=False)
    return controller.move_to(x, y)
