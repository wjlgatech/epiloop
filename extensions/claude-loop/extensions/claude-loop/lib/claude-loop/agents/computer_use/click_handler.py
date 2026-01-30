#!/usr/bin/env python3
"""
click_handler.py - Unified Click Handler with Fallback Chain

This module provides a unified click handler that automatically falls back
from AppleScript to vision-based clicking when needed. It integrates with:
- screenshot.py for screen capture
- vision_detector.py for element detection
- mouse_controller.py for coordinate-based clicking

Usage:
    from agents.computer_use.click_handler import ClickHandler

    handler = ClickHandler()
    result = handler.click_element(
        app_name="Unity",
        element_name="Build",
        vision_only=False  # Set True to skip AppleScript
    )
    if result.success:
        print(f"Clicked via {result.method} at ({result.x}, {result.y})")
"""

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Set up logging
logger = logging.getLogger(__name__)


class ClickMethod(Enum):
    """Method used to perform the click."""
    APPLESCRIPT = "applescript"
    VISION_COORDINATE = "vision_coordinate"
    DIRECT_COORDINATE = "direct_coordinate"
    FAILED = "failed"


class FallbackReason(Enum):
    """Reason for falling back to next method."""
    APPLESCRIPT_TIMEOUT = "applescript_timeout"
    APPLESCRIPT_ERROR = "applescript_error"
    ELEMENT_NOT_FOUND = "element_not_found"
    VISION_DISABLED = "vision_disabled"
    VISION_NOT_AVAILABLE = "vision_not_available"
    LOW_CONFIDENCE = "low_confidence"
    CLICK_FAILED = "click_failed"
    NONE = "none"


@dataclass
class ElementBounds:
    """Bounding box of a detected element."""
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates of the bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
        }


@dataclass
class ClickHandlerResult:
    """
    Detailed result from a click operation.

    Contains comprehensive information about the click attempt including:
    - Success/failure status
    - Method used (AppleScript or Vision+Coordinate)
    - Coordinates where click occurred
    - Confidence level (for vision-based clicks)
    - Before/after screenshots for verification
    - Fallback chain information
    """
    success: bool
    method: ClickMethod
    x: Optional[float] = None
    y: Optional[float] = None
    confidence: Optional[float] = None
    element_bounds: Optional[ElementBounds] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    # Fallback chain tracking
    applescript_tried: bool = False
    applescript_success: bool = False
    applescript_error: Optional[str] = None
    vision_tried: bool = False
    vision_success: bool = False
    vision_error: Optional[str] = None
    fallback_reason: FallbackReason = FallbackReason.NONE

    # Screenshots for verification
    before_screenshot: Optional[bytes] = None
    after_screenshot: Optional[bytes] = None
    before_screenshot_path: Optional[Path] = None
    after_screenshot_path: Optional[Path] = None

    # Additional metadata
    element_description: str = ""
    app_name: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        result = {
            "success": self.success,
            "method": self.method.value,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "applescript_tried": self.applescript_tried,
            "applescript_success": self.applescript_success,
            "applescript_error": self.applescript_error,
            "vision_tried": self.vision_tried,
            "vision_success": self.vision_success,
            "vision_error": self.vision_error,
            "fallback_reason": self.fallback_reason.value,
            "element_description": self.element_description,
            "app_name": self.app_name,
            "duration_ms": self.duration_ms,
        }
        if self.element_bounds:
            result["element_bounds"] = self.element_bounds.to_dict()
        if self.before_screenshot_path:
            result["before_screenshot_path"] = str(self.before_screenshot_path)
        if self.after_screenshot_path:
            result["after_screenshot_path"] = str(self.after_screenshot_path)
        return result

    def __repr__(self) -> str:
        if self.success:
            confidence_str = f", confidence={self.confidence:.2f}" if self.confidence else ""
            return (
                f"ClickHandlerResult(success=True, method={self.method.value}, "
                f"pos=({self.x}, {self.y}){confidence_str})"
            )
        return f"ClickHandlerResult(success=False, error='{self.error_message}')"


# Import availability flags and types
SCREENSHOT_AVAILABLE = False
VISION_DETECTOR_AVAILABLE = False
MOUSE_CONTROLLER_AVAILABLE = False
DEFAULT_SCREENSHOT_DIR = Path(".claude-loop/screenshots")

try:
    from .screenshot import (
        MultiMonitorCapture,
        DEFAULT_SCREENSHOT_DIR,
    )
    SCREENSHOT_AVAILABLE = True
except ImportError:
    MultiMonitorCapture = None  # type: ignore

try:
    from .vision_detector import VisionDetector
    VISION_DETECTOR_AVAILABLE = True
except ImportError:
    VisionDetector = None  # type: ignore

try:
    from .mouse_controller import MouseController
    MOUSE_CONTROLLER_AVAILABLE = True
except ImportError:
    MouseController = None  # type: ignore


class ClickHandler:
    """
    Unified click handler with automatic fallback chain.

    This class provides:
    - AppleScript-based clicking (fast path when available)
    - Vision-based element detection + coordinate clicking (fallback)
    - Before/after screenshot capture for verification
    - Support for --vision-only mode
    - Detailed result reporting

    Fallback Order:
    1. AppleScript (if vision_only=False)
    2. Vision API to find element + mouse_controller click

    Example:
        handler = ClickHandler()

        # Normal mode: tries AppleScript first, then vision
        result = handler.click_element("Unity", "Build")

        # Vision-only mode: skips AppleScript
        result = handler.click_element("Unity", "Build", vision_only=True)

        if result.success:
            print(f"Clicked at ({result.x}, {result.y})")
            print(f"Method: {result.method.value}")
            print(f"Confidence: {result.confidence}")
    """

    # Timing constants
    APPLESCRIPT_TIMEOUT = 5.0  # seconds
    CLICK_DELAY_BEFORE = 0.1  # seconds
    CLICK_DELAY_AFTER = 0.2  # seconds
    DEFAULT_MIN_CONFIDENCE = 0.7

    def __init__(
        self,
        vision_detector: Optional[Any] = None,
        screenshot_capture: Optional[Any] = None,
        mouse_controller: Optional[Any] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        enable_screenshots: bool = True,
        save_screenshots: bool = False,
        screenshot_dir: Optional[Path] = None,
    ):
        """
        Initialize the ClickHandler.

        Args:
            vision_detector: VisionDetector instance. If None, creates one when needed.
            screenshot_capture: MultiMonitorCapture instance. If None, creates one when needed.
            mouse_controller: MouseController instance. If None, creates one when needed.
            min_confidence: Minimum confidence threshold for vision detection.
            enable_screenshots: If True, capture before/after screenshots.
            save_screenshots: If True, save screenshots to disk.
            screenshot_dir: Directory to save screenshots. Defaults to .claude-loop/screenshots/.
        """
        self._vision_detector = vision_detector
        self._screenshot_capture = screenshot_capture
        self._mouse_controller = mouse_controller
        self._min_confidence = min_confidence
        self._enable_screenshots = enable_screenshots
        self._save_screenshots = save_screenshots
        self._screenshot_dir = screenshot_dir or DEFAULT_SCREENSHOT_DIR if SCREENSHOT_AVAILABLE else Path(".claude-loop/screenshots")

        # Lazy initialization flags
        self._vision_initialized = False
        self._screenshot_initialized = False
        self._mouse_initialized = False

    def _get_vision_detector(self) -> Optional[Any]:
        """Get or create the VisionDetector instance."""
        if not VISION_DETECTOR_AVAILABLE:
            logger.warning("VisionDetector not available - anthropic package not installed")
            return None

        if self._vision_detector is None and not self._vision_initialized:
            try:
                self._vision_detector = VisionDetector(
                    min_confidence=self._min_confidence
                )
                self._vision_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize VisionDetector: {e}")
                self._vision_initialized = True  # Don't retry

        return self._vision_detector

    def _get_screenshot_capture(self) -> Optional[Any]:
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

    def _get_mouse_controller(self) -> Optional[Any]:
        """Get or create the MouseController instance."""
        if not MOUSE_CONTROLLER_AVAILABLE:
            logger.warning("MouseController not available - Quartz not installed")
            return None

        if self._mouse_controller is None and not self._mouse_initialized:
            try:
                self._mouse_controller = MouseController()
                self._mouse_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize MouseController: {e}")
                self._mouse_initialized = True  # Don't retry

        return self._mouse_controller

    def click_element(
        self,
        app_name: str,
        element_name: str,
        window_name: str = "",
        vision_only: bool = False,
        capture_screenshots: bool = True,
    ) -> ClickHandlerResult:
        """
        Click a UI element with automatic fallback.

        Fallback chain:
        1. AppleScript (if vision_only=False) - Uses System Events accessibility
        2. Vision + Coordinate click - Uses Claude Vision API to find element,
           then clicks at the center of the detected bounding box

        Args:
            app_name: Application name (e.g., "Unity", "Safari").
            element_name: Name or description of the element to click.
            window_name: Optional window name to scope the search.
            vision_only: If True, skip AppleScript and use vision directly.
            capture_screenshots: If True, capture before/after screenshots.

        Returns:
            ClickHandlerResult with detailed information about the operation.
        """
        start_time = time.time()

        result = ClickHandlerResult(
            success=False,
            method=ClickMethod.FAILED,
            element_description=element_name,
            app_name=app_name,
        )

        # Capture before screenshot
        if capture_screenshots and self._enable_screenshots:
            self._capture_before_screenshot(result)

        # Step 1: Try AppleScript (if not vision_only)
        if not vision_only:
            result.applescript_tried = True
            logger.debug(f"Attempting AppleScript click: app={app_name}, element={element_name}")

            applescript_success, applescript_error = self._click_applescript(
                app_name=app_name,
                element_name=element_name,
                window_name=window_name,
            )

            if applescript_success:
                result.applescript_success = True
                result.success = True
                result.method = ClickMethod.APPLESCRIPT
                logger.info(f"AppleScript click succeeded for '{element_name}' in '{app_name}'")

                # Capture after screenshot
                if capture_screenshots and self._enable_screenshots:
                    time.sleep(self.CLICK_DELAY_AFTER)
                    self._capture_after_screenshot(result)

                result.duration_ms = int((time.time() - start_time) * 1000)
                return result

            # AppleScript failed, record why and continue to fallback
            result.applescript_error = applescript_error
            if "timeout" in (applescript_error or "").lower():
                result.fallback_reason = FallbackReason.APPLESCRIPT_TIMEOUT
            else:
                result.fallback_reason = FallbackReason.APPLESCRIPT_ERROR

            logger.debug(f"AppleScript failed: {applescript_error}, falling back to vision")

        else:
            # Vision-only mode
            result.fallback_reason = FallbackReason.VISION_DISABLED
            logger.debug("Vision-only mode: skipping AppleScript")

        # Step 2: Try Vision + Coordinate click
        result.vision_tried = True

        if not VISION_DETECTOR_AVAILABLE:
            result.vision_error = "Vision detector not available"
            result.error_message = "Both AppleScript and vision fallback failed"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        if not MOUSE_CONTROLLER_AVAILABLE:
            result.vision_error = "Mouse controller not available"
            result.error_message = "Vision found element but cannot click (no mouse controller)"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        vision_result = self._click_with_vision(
            app_name=app_name,
            element_name=element_name,
            window_name=window_name,
        )

        if vision_result.success:
            result.vision_success = True
            result.success = True
            result.method = ClickMethod.VISION_COORDINATE
            result.x = vision_result.x
            result.y = vision_result.y
            result.confidence = vision_result.confidence
            result.element_bounds = vision_result.element_bounds
            logger.info(
                f"Vision-based click succeeded for '{element_name}' at "
                f"({result.x}, {result.y}) with confidence {result.confidence:.2f}"
            )

            # Capture after screenshot
            if capture_screenshots and self._enable_screenshots:
                time.sleep(self.CLICK_DELAY_AFTER)
                self._capture_after_screenshot(result)

        else:
            result.vision_error = vision_result.error_message
            result.error_message = f"All click methods failed: {vision_result.error_message}"

            if vision_result.fallback_reason != FallbackReason.NONE:
                result.fallback_reason = vision_result.fallback_reason

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _click_applescript(
        self,
        app_name: str,
        element_name: str,
        window_name: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """
        Click a button using AppleScript.

        Args:
            app_name: Application name.
            element_name: Button/element name to click.
            window_name: Optional window name.

        Returns:
            Tuple of (success, error_message).
        """
        # Build AppleScript based on whether window name is provided
        if window_name and window_name.strip():
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    tell window "{window_name}"
                        click button "{element_name}"
                    end tell
                end tell
            end tell
            '''
        else:
            # Try multiple strategies for finding the button
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    try
                        click button "{element_name}" of window 1
                    on error
                        try
                            click button "{element_name}" of front window
                        on error
                            -- Try finding button anywhere in the UI
                            set foundButtons to every button of window 1 whose name is "{element_name}"
                            if (count of foundButtons) > 0 then
                                click item 1 of foundButtons
                            else
                                error "Button not found"
                            end if
                        end try
                    end try
                end tell
            end tell
            '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self.APPLESCRIPT_TIMEOUT,
            )

            if result.returncode == 0:
                return (True, None)
            else:
                error_msg = result.stderr.strip() or "Unknown AppleScript error"
                return (False, error_msg)

        except subprocess.TimeoutExpired:
            return (False, f"AppleScript timeout after {self.APPLESCRIPT_TIMEOUT}s")
        except subprocess.SubprocessError as e:
            return (False, f"AppleScript subprocess error: {e}")
        except Exception as e:
            return (False, f"AppleScript error: {e}")

    def _click_with_vision(
        self,
        app_name: str,
        element_name: str,
        window_name: str = "",
    ) -> ClickHandlerResult:
        """
        Find element using vision and click at its coordinates.

        Args:
            app_name: Application name for context.
            element_name: Description of the element to find.
            window_name: Optional window name for context.

        Returns:
            ClickHandlerResult with vision detection and click results.
        """
        result = ClickHandlerResult(
            success=False,
            method=ClickMethod.FAILED,
            element_description=element_name,
            app_name=app_name,
        )

        # Get components
        vision_detector = self._get_vision_detector()
        screenshot_capture = self._get_screenshot_capture()
        mouse_controller = self._get_mouse_controller()

        if vision_detector is None:
            result.error_message = "Vision detector not available"
            result.fallback_reason = FallbackReason.VISION_NOT_AVAILABLE
            return result

        if screenshot_capture is None:
            result.error_message = "Screenshot capture not available"
            result.fallback_reason = FallbackReason.VISION_NOT_AVAILABLE
            return result

        if mouse_controller is None:
            result.error_message = "Mouse controller not available"
            return result

        # Capture screenshot
        try:
            screenshot_result = screenshot_capture.capture_all_displays()
        except Exception as e:
            result.error_message = f"Failed to capture screenshot: {e}"
            return result

        # Build search query with context
        search_query = element_name
        if app_name:
            search_query = f"the '{element_name}' button in {app_name}"
        if window_name:
            search_query = f"{search_query} ({window_name} window)"

        # Find element using vision
        try:
            detection = vision_detector.find_element(
                screenshot=screenshot_result.image_bytes,
                element_description=search_query,
                screenshot_width=screenshot_result.width,
                screenshot_height=screenshot_result.height,
            )
        except Exception as e:
            result.error_message = f"Vision API error: {e}"
            return result

        if detection is None:
            result.error_message = f"Element '{element_name}' not found in screenshot"
            result.fallback_reason = FallbackReason.ELEMENT_NOT_FOUND
            return result

        # Check confidence
        if detection.confidence < self._min_confidence:
            result.error_message = (
                f"Element found but confidence {detection.confidence:.2f} "
                f"below threshold {self._min_confidence}"
            )
            result.fallback_reason = FallbackReason.LOW_CONFIDENCE
            result.confidence = detection.confidence
            return result

        result.confidence = detection.confidence

        # Convert detection coordinates to screen coordinates
        # The vision detector returns coordinates in screenshot space
        # We need to convert to global screen coordinates
        try:
            screen_x, screen_y = screenshot_capture.screenshot_coords_to_screen(
                screenshot_x=detection.x,
                screenshot_y=detection.y,
                screenshot_result=screenshot_result,
            )
        except Exception as e:
            result.error_message = f"Failed to convert coordinates: {e}"
            return result

        result.x = screen_x
        result.y = screen_y

        # Store bounding box if available
        if detection.bounding_box:
            result.element_bounds = ElementBounds(
                x=detection.bounding_box.x,
                y=detection.bounding_box.y,
                width=detection.bounding_box.width,
                height=detection.bounding_box.height,
            )

        # Click at the coordinates
        logger.debug(f"Clicking at screen coordinates ({screen_x}, {screen_y})")
        time.sleep(self.CLICK_DELAY_BEFORE)

        click_result = mouse_controller.click_at(screen_x, screen_y, verify=True)

        if click_result.success:
            result.success = True
            result.method = ClickMethod.VISION_COORDINATE
            logger.debug(f"Vision-based click succeeded at ({screen_x}, {screen_y})")
        else:
            result.error_message = f"Mouse click failed: {click_result.error}"
            result.fallback_reason = FallbackReason.CLICK_FAILED
            logger.warning(f"Mouse click failed at ({screen_x}, {screen_y}): {click_result.error}")

        return result

    def _capture_before_screenshot(self, result: ClickHandlerResult) -> None:
        """Capture before screenshot and optionally save to disk."""
        capture = self._get_screenshot_capture()
        if capture is None:
            return

        try:
            screenshot_result = capture.capture_all_displays()
            result.before_screenshot = screenshot_result.image_bytes

            if self._save_screenshots and result.before_screenshot is not None:
                self._screenshot_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = self._screenshot_dir / f"before_{timestamp}.png"
                path.write_bytes(result.before_screenshot)
                result.before_screenshot_path = path
                logger.debug(f"Saved before screenshot to {path}")

        except Exception as e:
            logger.warning(f"Failed to capture before screenshot: {e}")

    def _capture_after_screenshot(self, result: ClickHandlerResult) -> None:
        """Capture after screenshot and optionally save to disk."""
        capture = self._get_screenshot_capture()
        if capture is None:
            return

        try:
            screenshot_result = capture.capture_all_displays()
            result.after_screenshot = screenshot_result.image_bytes

            if self._save_screenshots and result.after_screenshot is not None:
                self._screenshot_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = self._screenshot_dir / f"after_{timestamp}.png"
                path.write_bytes(result.after_screenshot)
                result.after_screenshot_path = path
                logger.debug(f"Saved after screenshot to {path}")

        except Exception as e:
            logger.warning(f"Failed to capture after screenshot: {e}")

    def set_min_confidence(self, threshold: float) -> None:
        """
        Set the minimum confidence threshold for vision detection.

        Args:
            threshold: Value between 0.0 and 1.0.
        """
        self._min_confidence = threshold
        if self._vision_detector is not None:
            self._vision_detector.set_min_confidence(threshold)


# Convenience functions

def click_element(
    app_name: str,
    element_name: str,
    window_name: str = "",
    vision_only: bool = False,
    min_confidence: float = 0.7,
) -> ClickHandlerResult:
    """
    Click a UI element with automatic fallback.

    Convenience function that creates a ClickHandler instance and performs
    a single click operation. For multiple clicks, create a ClickHandler
    instance directly to benefit from caching.

    Args:
        app_name: Application name (e.g., "Unity", "Safari").
        element_name: Name or description of the element to click.
        window_name: Optional window name to scope the search.
        vision_only: If True, skip AppleScript and use vision directly.
        min_confidence: Minimum confidence threshold for vision detection.

    Returns:
        ClickHandlerResult with detailed information about the operation.
    """
    handler = ClickHandler(min_confidence=min_confidence)
    return handler.click_element(
        app_name=app_name,
        element_name=element_name,
        window_name=window_name,
        vision_only=vision_only,
    )


def click_element_vision_only(
    app_name: str,
    element_name: str,
    window_name: str = "",
    min_confidence: float = 0.7,
) -> ClickHandlerResult:
    """
    Click a UI element using vision-based detection only (skip AppleScript).

    Convenience function for when AppleScript is known to not work for
    a particular application or element.

    Args:
        app_name: Application name (e.g., "Unity", "Safari").
        element_name: Name or description of the element to click.
        window_name: Optional window name to scope the search.
        min_confidence: Minimum confidence threshold for vision detection.

    Returns:
        ClickHandlerResult with detailed information about the operation.
    """
    return click_element(
        app_name=app_name,
        element_name=element_name,
        window_name=window_name,
        vision_only=True,
        min_confidence=min_confidence,
    )


# Availability flag
CLICK_HANDLER_AVAILABLE = SCREENSHOT_AVAILABLE and (VISION_DETECTOR_AVAILABLE or True)

__all__ = [
    # Main class
    "ClickHandler",
    # Result types
    "ClickHandlerResult",
    "ClickMethod",
    "FallbackReason",
    "ElementBounds",
    # Convenience functions
    "click_element",
    "click_element_vision_only",
    # Availability flag
    "CLICK_HANDLER_AVAILABLE",
]
