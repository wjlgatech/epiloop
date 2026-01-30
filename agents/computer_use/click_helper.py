#!/usr/bin/env python3
"""
click_helper.py - Click operations with vision-based fallback

This module provides click functionality that first attempts AppleScript-based
clicking (fast path), then falls back to vision-based element detection and
Quartz CGEventCreateMouseEvent for direct mouse control.

Usage:
    from agents.computer_use.click_helper import ClickHelper

    helper = ClickHelper()
    result = helper.click_element(
        app_name="Unity",
        element_description="the Build button",
        vision_fallback=True
    )
    if result.success:
        print(f"Clicked at ({result.x}, {result.y}) via {result.method}")
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Callable, Any

# Platform-specific imports with fallbacks
try:
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventPost,
        CGEventSetIntegerValueField,
        kCGHIDEventTap,
        kCGMouseButtonLeft,
        kCGEventMouseMoved,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged,
    )
    from Quartz.CoreGraphics import (
        kCGMouseEventClickState,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

# Import vision finder if available
try:
    from .vision_finder import VisionElementFinder, ElementLocation
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

# Import screenshot capture if available
try:
    from .screenshot import MultiMonitorCapture, ScreenshotResult
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False


# Set up logging
logger = logging.getLogger(__name__)


class ClickMethod(Enum):
    """Method used to perform the click."""
    APPLESCRIPT = "applescript"
    VISION_QUARTZ = "vision_quartz"
    COORDINATES = "coordinates"
    FAILED = "failed"


@dataclass
class ClickResult:
    """Result of a click operation."""
    success: bool
    method: ClickMethod
    x: Optional[float] = None
    y: Optional[float] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    applescript_tried: bool = False
    vision_tried: bool = False
    before_screenshot: Optional[bytes] = None
    after_screenshot: Optional[bytes] = None

    def __repr__(self) -> str:
        if self.success:
            return f"ClickResult(success=True, method={self.method.value}, pos=({self.x}, {self.y}))"
        return f"ClickResult(success=False, error='{self.error_message}')"


class ClickHelper:
    """
    Helper class for click operations with vision-based fallback.

    Provides a multi-strategy approach to clicking UI elements:
    1. AppleScript (fast path) - Uses System Events accessibility API
    2. Vision + Quartz (fallback) - Uses Claude Vision to find elements
       and Quartz events for mouse clicks
    """

    # Timing constants
    CLICK_DELAY_BEFORE = 0.1  # Delay before clicking
    CLICK_DELAY_AFTER = 0.2  # Delay after clicking
    DOUBLE_CLICK_INTERVAL = 0.1  # Interval between double click events

    def __init__(
        self,
        vision_finder: Optional['VisionElementFinder'] = None,
        screenshot_capture: Optional['MultiMonitorCapture'] = None,
        applescript_timeout: float = 5.0,
        min_vision_confidence: float = 0.7,
        enable_verification: bool = True,
    ):
        """
        Initialize the ClickHelper.

        Args:
            vision_finder: VisionElementFinder instance for element detection.
                          If None, will create one when needed (requires API key).
            screenshot_capture: MultiMonitorCapture instance for screenshots.
                               If None, will create one when needed.
            applescript_timeout: Timeout for AppleScript commands.
            min_vision_confidence: Minimum confidence for vision-based detection.
            enable_verification: If True, capture before/after screenshots.
        """
        self._vision_finder = vision_finder
        self._screenshot_capture = screenshot_capture
        self._applescript_timeout = applescript_timeout
        self._min_vision_confidence = min_vision_confidence
        self._enable_verification = enable_verification

        # Lazy initialization flags
        self._vision_initialized = False
        self._screenshot_initialized = False

    def _get_vision_finder(self) -> Optional['VisionElementFinder']:
        """Get or create the VisionElementFinder instance."""
        if not VISION_AVAILABLE:
            logger.warning("Vision finder not available - anthropic package not installed")
            return None

        if self._vision_finder is None and not self._vision_initialized:
            try:
                self._vision_finder = VisionElementFinder(
                    min_confidence=self._min_vision_confidence
                )
                self._vision_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize VisionElementFinder: {e}")
                self._vision_initialized = True  # Don't retry

        return self._vision_finder

    def _get_screenshot_capture(self) -> Optional['MultiMonitorCapture']:
        """Get or create the MultiMonitorCapture instance."""
        if not SCREENSHOT_AVAILABLE:
            logger.warning("Screenshot capture not available - Quartz/PIL not installed")
            return None

        if self._screenshot_capture is None and not self._screenshot_initialized:
            try:
                self._screenshot_capture = MultiMonitorCapture()
                self._screenshot_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize MultiMonitorCapture: {e}")
                self._screenshot_initialized = True  # Don't retry

        return self._screenshot_capture

    def click_element(
        self,
        app_name: str,
        element_description: str,
        window_name: str = "",
        vision_fallback: bool = True,
        capture_verification: bool = True,
    ) -> ClickResult:
        """
        Click a UI element, with optional vision-based fallback.

        This method first attempts to click using AppleScript (fast path).
        If that fails and vision_fallback is True, it will:
        1. Capture a screenshot
        2. Use Claude Vision to find the element
        3. Click at the found coordinates using Quartz events

        Args:
            app_name: Name of the application (e.g., "Unity", "Finder")
            element_description: Description of element for AppleScript or vision
            window_name: Optional window name to scope the search
            vision_fallback: If True, use vision-based detection on AppleScript failure
            capture_verification: If True, capture before/after screenshots

        Returns:
            ClickResult with success status and details
        """
        result = ClickResult(
            success=False,
            method=ClickMethod.FAILED
        )

        # Capture before screenshot if verification enabled
        if capture_verification and self._enable_verification:
            result.before_screenshot = self._capture_screenshot()

        # Try AppleScript first (fast path)
        logger.debug(f"Attempting AppleScript click: app={app_name}, element={element_description}")
        result.applescript_tried = True

        applescript_success = self._click_applescript(
            app_name=app_name,
            button_name=element_description,
            window_name=window_name
        )

        if applescript_success:
            logger.info(f"AppleScript click succeeded for '{element_description}'")
            result.success = True
            result.method = ClickMethod.APPLESCRIPT

            # Capture after screenshot
            if capture_verification and self._enable_verification:
                time.sleep(self.CLICK_DELAY_AFTER)
                result.after_screenshot = self._capture_screenshot()

            return result

        logger.debug(f"AppleScript click failed for '{element_description}'")

        # Try vision-based fallback if enabled
        if not vision_fallback:
            result.error_message = "AppleScript click failed and vision fallback disabled"
            return result

        if not QUARTZ_AVAILABLE:
            result.error_message = "Vision fallback requires Quartz framework"
            return result

        logger.debug(f"Attempting vision-based click for '{element_description}'")
        result.vision_tried = True

        # Find element using vision
        element_location = self._find_element_with_vision(
            element_description=element_description,
            app_name=app_name,
            window_name=window_name
        )

        if element_location is None:
            result.error_message = "Element not found by vision API"
            return result

        logger.info(
            f"Vision found element at ({element_location.x}, {element_location.y}) "
            f"with confidence {element_location.confidence:.2f}"
        )

        result.x = element_location.x
        result.y = element_location.y
        result.confidence = element_location.confidence

        # Perform click using Quartz events
        click_success = self._click_at_coordinates(
            x=element_location.x,
            y=element_location.y
        )

        if click_success:
            logger.info(f"Vision-based click succeeded at ({result.x}, {result.y})")
            result.success = True
            result.method = ClickMethod.VISION_QUARTZ

            # Capture after screenshot
            if capture_verification and self._enable_verification:
                time.sleep(self.CLICK_DELAY_AFTER)
                result.after_screenshot = self._capture_screenshot()
        else:
            result.error_message = "Quartz click event failed"

        return result

    def click_at(
        self,
        x: float,
        y: float,
        capture_verification: bool = True,
    ) -> ClickResult:
        """
        Click at specific screen coordinates using Quartz events.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
            capture_verification: If True, capture before/after screenshots

        Returns:
            ClickResult with success status
        """
        result = ClickResult(
            success=False,
            method=ClickMethod.FAILED,
            x=x,
            y=y
        )

        if not QUARTZ_AVAILABLE:
            result.error_message = "Quartz framework not available"
            return result

        # Capture before screenshot
        if capture_verification and self._enable_verification:
            result.before_screenshot = self._capture_screenshot()

        # Perform click
        click_success = self._click_at_coordinates(x=x, y=y)

        if click_success:
            result.success = True
            result.method = ClickMethod.COORDINATES

            # Capture after screenshot
            if capture_verification and self._enable_verification:
                time.sleep(self.CLICK_DELAY_AFTER)
                result.after_screenshot = self._capture_screenshot()
        else:
            result.error_message = "Quartz click event failed"

        return result

    def double_click_at(
        self,
        x: float,
        y: float,
        capture_verification: bool = True,
    ) -> ClickResult:
        """
        Double-click at specific screen coordinates using Quartz events.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
            capture_verification: If True, capture before/after screenshots

        Returns:
            ClickResult with success status
        """
        result = ClickResult(
            success=False,
            method=ClickMethod.FAILED,
            x=x,
            y=y
        )

        if not QUARTZ_AVAILABLE:
            result.error_message = "Quartz framework not available"
            return result

        # Capture before screenshot
        if capture_verification and self._enable_verification:
            result.before_screenshot = self._capture_screenshot()

        # Perform double click
        click_success = self._double_click_at_coordinates(x=x, y=y)

        if click_success:
            result.success = True
            result.method = ClickMethod.COORDINATES

            # Capture after screenshot
            if capture_verification and self._enable_verification:
                time.sleep(self.CLICK_DELAY_AFTER)
                result.after_screenshot = self._capture_screenshot()
        else:
            result.error_message = "Quartz double-click event failed"

        return result

    def _click_applescript(
        self,
        app_name: str,
        button_name: str,
        window_name: str = ""
    ) -> bool:
        """
        Click a button using AppleScript.

        Args:
            app_name: Application name
            button_name: Button name/title to click
            window_name: Optional window name

        Returns:
            True if click succeeded
        """
        if window_name and window_name.strip():
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    tell window "{window_name}"
                        click button "{button_name}"
                    end tell
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    click button "{button_name}" of window 1
                end tell
            end tell
            '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self._applescript_timeout
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _find_element_with_vision(
        self,
        element_description: str,
        app_name: str = "",
        window_name: str = ""
    ) -> Optional['ElementLocation']:
        """
        Find an element using vision-based detection.

        Args:
            element_description: Description of the element to find
            app_name: Optional app name for context
            window_name: Optional window name for context

        Returns:
            ElementLocation if found, None otherwise
        """
        vision_finder = self._get_vision_finder()
        if vision_finder is None:
            logger.warning("Vision finder not available")
            return None

        screenshot_capture = self._get_screenshot_capture()
        if screenshot_capture is None:
            logger.warning("Screenshot capture not available")
            return None

        # Capture screenshot
        try:
            screenshot_result = screenshot_capture.capture_all_displays()
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

        # Build search query with context
        search_query = element_description
        if app_name:
            search_query = f"{search_query} in {app_name}"
        if window_name:
            search_query = f"{search_query} ({window_name} window)"

        # Find element
        try:
            element = vision_finder.find_element(
                screenshot_bytes=screenshot_result.image_bytes,
                element_description=search_query,
                screenshot_width=screenshot_result.width,
                screenshot_height=screenshot_result.height
            )
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            return None

        if element is None:
            return None

        # Convert screenshot coordinates to screen coordinates
        screen_x, screen_y = screenshot_capture.screenshot_coords_to_screen(
            screenshot_x=element.x,
            screenshot_y=element.y,
            screenshot_result=screenshot_result
        )

        # Return element with screen coordinates
        return ElementLocation(
            x=int(screen_x),
            y=int(screen_y),
            confidence=element.confidence,
            description=element.description,
            bounding_box=element.bounding_box,
            element_type=element.element_type
        )

    def _click_at_coordinates(self, x: float, y: float) -> bool:
        """
        Perform a mouse click at screen coordinates using Quartz events.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate

        Returns:
            True if successful
        """
        if not QUARTZ_AVAILABLE:
            return False

        try:
            point = (x, y)

            # Small delay before clicking
            time.sleep(self.CLICK_DELAY_BEFORE)

            # Move mouse to position
            move_event = CGEventCreateMouseEvent(
                None,
                kCGEventMouseMoved,
                point,
                kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, move_event)
            time.sleep(0.05)

            # Mouse down
            down_event = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseDown,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(down_event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, down_event)

            # Small delay between down and up
            time.sleep(0.02)

            # Mouse up
            up_event = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseUp,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(up_event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, up_event)

            logger.debug(f"Quartz click at ({x}, {y}) completed")
            return True

        except Exception as e:
            logger.error(f"Quartz click failed: {e}")
            return False

    def _double_click_at_coordinates(self, x: float, y: float) -> bool:
        """
        Perform a double-click at screen coordinates using Quartz events.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate

        Returns:
            True if successful
        """
        if not QUARTZ_AVAILABLE:
            return False

        try:
            point = (x, y)

            # Small delay before clicking
            time.sleep(self.CLICK_DELAY_BEFORE)

            # Move mouse to position
            move_event = CGEventCreateMouseEvent(
                None,
                kCGEventMouseMoved,
                point,
                kCGMouseButtonLeft
            )
            CGEventPost(kCGHIDEventTap, move_event)
            time.sleep(0.05)

            # First click
            down_event1 = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseDown,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(down_event1, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, down_event1)
            time.sleep(0.02)

            up_event1 = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseUp,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(up_event1, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, up_event1)

            # Brief pause between clicks
            time.sleep(self.DOUBLE_CLICK_INTERVAL)

            # Second click (with click count = 2)
            down_event2 = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseDown,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(down_event2, kCGMouseEventClickState, 2)
            CGEventPost(kCGHIDEventTap, down_event2)
            time.sleep(0.02)

            up_event2 = CGEventCreateMouseEvent(
                None,
                kCGEventLeftMouseUp,
                point,
                kCGMouseButtonLeft
            )
            CGEventSetIntegerValueField(up_event2, kCGMouseEventClickState, 2)
            CGEventPost(kCGHIDEventTap, up_event2)

            logger.debug(f"Quartz double-click at ({x}, {y}) completed")
            return True

        except Exception as e:
            logger.error(f"Quartz double-click failed: {e}")
            return False

    def _capture_screenshot(self) -> Optional[bytes]:
        """Capture a screenshot for verification."""
        capture = self._get_screenshot_capture()
        if capture is None:
            return None

        try:
            result = capture.capture_all_displays()
            return result.image_bytes
        except Exception as e:
            logger.warning(f"Failed to capture verification screenshot: {e}")
            return None


# Convenience function for simple usage
def click_with_vision_fallback(
    app_name: str,
    element_description: str,
    window_name: str = "",
    enable_verification: bool = True
) -> ClickResult:
    """
    Click a UI element with vision-based fallback.

    Args:
        app_name: Application name (e.g., "Unity")
        element_description: Description of the element to click
        window_name: Optional window name
        enable_verification: If True, capture before/after screenshots

    Returns:
        ClickResult with success status and details
    """
    helper = ClickHelper(enable_verification=enable_verification)
    return helper.click_element(
        app_name=app_name,
        element_description=element_description,
        window_name=window_name,
        vision_fallback=True,
        capture_verification=enable_verification
    )
