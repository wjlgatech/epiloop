#!/usr/bin/env python3
"""
wait_utils.py - Wait-for-UI-State Utilities

This module provides utilities for waiting for UI elements to appear, disappear,
or change state. It replaces arbitrary sleep() calls with intelligent polling
that uses the Vision API to detect when conditions are met.

Usage:
    from agents.computer_use.wait_utils import (
        wait_for_element,
        wait_for_element_gone,
        wait_for_text,
        wait_for_button_enabled,
    )

    # Wait for a button to appear
    result = wait_for_element("the 'Build' button", timeout=10.0)
    if result.success:
        print(f"Button found at ({result.element.x}, {result.element.y})")

    # Wait for a loading spinner to disappear
    result = wait_for_element_gone("loading spinner", timeout=30.0)

    # Wait for specific text to appear
    result = wait_for_text("Build successful", timeout=60.0)

    # Wait for a button to become enabled
    result = wait_for_button_enabled("Submit", timeout=15.0)

    # Custom predicate
    def is_progress_complete(state):
        return state and state.progress_value and state.progress_value >= 1.0

    result = wait_for_condition(
        "progress bar",
        predicate=is_progress_complete,
        timeout=120.0,
    )
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any, List

# Conditional imports with availability flags
try:
    from .vision_detector import (
        VisionDetector,
        DetectionResult as DetectionResultType,
        ElementState as ElementStateType,
        ButtonState,
        VISION_DETECTOR_AVAILABLE,
    )
except ImportError:
    VISION_DETECTOR_AVAILABLE = False  # type: ignore
    VisionDetector = None  # type: ignore
    DetectionResultType = None  # type: ignore
    ElementStateType = None  # type: ignore
    ButtonState = None  # type: ignore

try:
    from .screenshot import MultiMonitorCapture, QUARTZ_AVAILABLE
    SCREENSHOT_AVAILABLE = QUARTZ_AVAILABLE
except ImportError:
    SCREENSHOT_AVAILABLE = False
    MultiMonitorCapture = None  # type: ignore

# Logger for wait operations
logger = logging.getLogger(__name__)


class WaitOutcome(Enum):
    """Outcome of a wait operation."""
    SUCCESS = "success"  # Condition was met
    TIMEOUT = "timeout"  # Timed out waiting
    ERROR = "error"  # Error occurred during wait
    CANCELLED = "cancelled"  # Wait was cancelled


@dataclass
class WaitProgress:
    """Progress information for a single poll iteration."""
    iteration: int
    elapsed_ms: float
    remaining_ms: float
    found: bool
    element: Optional[Any] = None  # DetectionResult or ElementState
    message: str = ""


@dataclass
class WaitResult:
    """Result of a wait operation."""
    success: bool
    outcome: WaitOutcome
    element: Optional[Any] = None  # DetectionResult or ElementState if found
    elapsed_ms: float = 0.0
    iterations: int = 0
    last_error: Optional[str] = None
    progress_log: List[WaitProgress] = field(default_factory=list)

    # Timestamp when wait completed
    completed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "success": self.success,
            "outcome": self.outcome.value,
            "elapsed_ms": self.elapsed_ms,
            "iterations": self.iterations,
            "completed_at": self.completed_at.isoformat(),
        }
        if self.element:
            if hasattr(self.element, "to_dict"):
                result["element"] = self.element.to_dict()
            else:
                result["element"] = str(self.element)
        if self.last_error:
            result["last_error"] = self.last_error
        return result


# Type for predicate functions
PredicateFunc = Callable[[Optional[Any]], bool]


class WaitHelper:
    """
    Helper class for waiting for UI elements and conditions.

    This class provides methods for:
    - Waiting for elements to appear in screenshots
    - Waiting for elements to disappear
    - Waiting for specific text to appear
    - Waiting for elements to reach specific states (enabled, checked, etc.)
    - Waiting for custom conditions via predicates

    Uses vision API polling with configurable intervals and timeouts.
    """

    # Default configuration
    DEFAULT_TIMEOUT_S = 10.0  # Default timeout in seconds
    DEFAULT_POLL_INTERVAL_S = 0.5  # Default polling interval in seconds
    DEFAULT_MIN_CONFIDENCE = 0.7  # Minimum confidence for detection

    def __init__(
        self,
        vision_detector: Optional[Any] = None,
        screenshot_capture: Optional[Any] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_S,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        log_progress: bool = True,
    ):
        """
        Initialize the WaitHelper.

        Args:
            vision_detector: Optional VisionDetector instance. If None, creates new one.
            screenshot_capture: Optional MultiMonitorCapture instance. If None, creates new one.
            poll_interval: Default polling interval in seconds.
            min_confidence: Minimum confidence threshold for element detection.
            log_progress: Whether to log progress during waits.
        """
        self._poll_interval = poll_interval
        self._min_confidence = min_confidence
        self._log_progress = log_progress

        # Initialize vision detector
        if vision_detector is not None:
            self._detector = vision_detector
        elif VISION_DETECTOR_AVAILABLE and VisionDetector is not None:
            self._detector = VisionDetector(min_confidence=min_confidence)
        else:
            self._detector = None

        # Initialize screenshot capture
        if screenshot_capture is not None:
            self._capture = screenshot_capture
        elif SCREENSHOT_AVAILABLE and MultiMonitorCapture is not None:
            self._capture = MultiMonitorCapture()
        else:
            self._capture = None

        # Track if we're in a wait operation (for cancellation)
        self._cancel_requested = False

    def _check_dependencies(self) -> Optional[str]:
        """Check if required dependencies are available. Returns error message if not."""
        if not VISION_DETECTOR_AVAILABLE:
            return "VisionDetector not available. Install anthropic package."
        if not SCREENSHOT_AVAILABLE:
            return "Screenshot capture not available. Install Quartz (macOS only)."
        if self._detector is None:
            return "VisionDetector not initialized."
        if self._capture is None:
            return "Screenshot capture not initialized."
        return None

    def _capture_screenshot(self) -> Optional[bytes]:
        """Capture a screenshot and return as PNG bytes."""
        if self._capture is None:
            return None

        try:
            result = self._capture.capture_all_displays()
            if result and result.image_bytes:
                return result.image_bytes
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")

        return None

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message if logging is enabled."""
        if not self._log_progress:
            return

        if level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)

    def cancel(self) -> None:
        """Request cancellation of the current wait operation."""
        self._cancel_requested = True

    def wait_for_element(
        self,
        element_description: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
    ) -> WaitResult:
        """
        Wait for a UI element to appear in the screenshot.

        Args:
            element_description: Natural language description of the element.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds. Uses default if None.

        Returns:
            WaitResult with success=True if element found, False on timeout.

        Raises:
            TimeoutError: If timeout is exceeded (when raise_on_timeout=True).
        """
        interval = poll_interval or self._poll_interval

        # Check dependencies
        error = self._check_dependencies()
        if error:
            return WaitResult(
                success=False,
                outcome=WaitOutcome.ERROR,
                last_error=error,
            )

        self._cancel_requested = False
        start_time = time.time()
        iteration = 0
        progress_log: List[WaitProgress] = []
        last_error: Optional[str] = None

        self._log(f"Waiting for element: '{element_description}' (timeout={timeout}s)")

        while True:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            # Check for cancellation
            if self._cancel_requested:
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.CANCELLED,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    progress_log=progress_log,
                )

            # Check for timeout
            if elapsed >= timeout:
                self._log(f"Timeout waiting for element: '{element_description}'", "warning")
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.TIMEOUT,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    last_error=last_error,
                    progress_log=progress_log,
                )

            # Capture screenshot and look for element
            try:
                screenshot = self._capture_screenshot()
                if screenshot is None:
                    last_error = "Failed to capture screenshot"
                    continue

                assert self._detector is not None  # Checked by _check_dependencies
                result = self._detector.find_element(screenshot, element_description)

                progress = WaitProgress(
                    iteration=iteration,
                    elapsed_ms=elapsed * 1000,
                    remaining_ms=remaining * 1000,
                    found=result is not None,
                    element=result,
                    message=f"Found: {result is not None}",
                )
                progress_log.append(progress)

                if result is not None:
                    self._log(
                        f"Element found after {elapsed:.2f}s ({iteration} iterations): "
                        f"({result.x}, {result.y}) confidence={result.confidence:.2f}"
                    )
                    return WaitResult(
                        success=True,
                        outcome=WaitOutcome.SUCCESS,
                        element=result,
                        elapsed_ms=elapsed * 1000,
                        iterations=iteration,
                        progress_log=progress_log,
                    )

                self._log(
                    f"Element not found, retrying... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                    "debug",
                )

            except Exception as e:
                last_error = str(e)
                self._log(f"Error during wait: {e}", "error")

            # Wait before next poll
            time.sleep(interval)

    def wait_for_element_gone(
        self,
        element_description: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
    ) -> WaitResult:
        """
        Wait for a UI element to disappear from the screenshot.

        Args:
            element_description: Natural language description of the element.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds.

        Returns:
            WaitResult with success=True if element disappeared, False on timeout.
        """
        interval = poll_interval or self._poll_interval

        # Check dependencies
        error = self._check_dependencies()
        if error:
            return WaitResult(
                success=False,
                outcome=WaitOutcome.ERROR,
                last_error=error,
            )

        self._cancel_requested = False
        start_time = time.time()
        iteration = 0
        progress_log: List[WaitProgress] = []
        last_error: Optional[str] = None

        self._log(f"Waiting for element to disappear: '{element_description}' (timeout={timeout}s)")

        while True:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            # Check for cancellation
            if self._cancel_requested:
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.CANCELLED,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    progress_log=progress_log,
                )

            # Check for timeout
            if elapsed >= timeout:
                self._log(f"Timeout waiting for element to disappear: '{element_description}'", "warning")
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.TIMEOUT,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    last_error=last_error,
                    progress_log=progress_log,
                )

            # Capture screenshot and look for element
            try:
                screenshot = self._capture_screenshot()
                if screenshot is None:
                    last_error = "Failed to capture screenshot"
                    continue

                assert self._detector is not None  # Checked by _check_dependencies
                result = self._detector.find_element(screenshot, element_description)

                progress = WaitProgress(
                    iteration=iteration,
                    elapsed_ms=elapsed * 1000,
                    remaining_ms=remaining * 1000,
                    found=result is not None,
                    element=result,
                    message=f"Still present: {result is not None}",
                )
                progress_log.append(progress)

                if result is None:
                    self._log(
                        f"Element disappeared after {elapsed:.2f}s ({iteration} iterations)"
                    )
                    return WaitResult(
                        success=True,
                        outcome=WaitOutcome.SUCCESS,
                        elapsed_ms=elapsed * 1000,
                        iterations=iteration,
                        progress_log=progress_log,
                    )

                self._log(
                    f"Element still present, waiting... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                    "debug",
                )

            except Exception as e:
                last_error = str(e)
                self._log(f"Error during wait: {e}", "error")

            # Wait before next poll
            time.sleep(interval)

    def wait_for_text(
        self,
        text: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
        case_sensitive: bool = True,
    ) -> WaitResult:
        """
        Wait for specific text to appear anywhere in the screenshot.

        Args:
            text: The text to wait for.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds.
            case_sensitive: Whether to match case exactly.

        Returns:
            WaitResult with success=True if text found, False on timeout.
        """
        # Build description for text search
        if case_sensitive:
            description = f"text saying exactly '{text}'"
        else:
            description = f"text saying '{text}' (case insensitive)"

        return self.wait_for_element(
            element_description=description,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def wait_for_button_enabled(
        self,
        button_text: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
    ) -> WaitResult:
        """
        Wait for a button to become enabled.

        Args:
            button_text: The text on the button.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds.

        Returns:
            WaitResult with success=True if button becomes enabled, False on timeout.
        """
        interval = poll_interval or self._poll_interval

        # Check dependencies
        error = self._check_dependencies()
        if error:
            return WaitResult(
                success=False,
                outcome=WaitOutcome.ERROR,
                last_error=error,
            )

        self._cancel_requested = False
        start_time = time.time()
        iteration = 0
        progress_log: List[WaitProgress] = []
        last_error: Optional[str] = None

        self._log(f"Waiting for button '{button_text}' to be enabled (timeout={timeout}s)")

        while True:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            # Check for cancellation
            if self._cancel_requested:
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.CANCELLED,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    progress_log=progress_log,
                )

            # Check for timeout
            if elapsed >= timeout:
                self._log(f"Timeout waiting for button '{button_text}' to be enabled", "warning")
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.TIMEOUT,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    last_error=last_error,
                    progress_log=progress_log,
                )

            # Capture screenshot and check button state
            try:
                screenshot = self._capture_screenshot()
                if screenshot is None:
                    last_error = "Failed to capture screenshot"
                    continue

                assert self._detector is not None  # Checked by _check_dependencies
                state = self._detector.get_button_state(screenshot, button_text)

                progress = WaitProgress(
                    iteration=iteration,
                    elapsed_ms=elapsed * 1000,
                    remaining_ms=remaining * 1000,
                    found=state is not None,
                    element=state,
                    message=f"Button state: {state.button_state.value if state and state.button_state else 'unknown'}",
                )
                progress_log.append(progress)

                if state is not None and state.is_enabled:
                    self._log(
                        f"Button '{button_text}' is now enabled after {elapsed:.2f}s ({iteration} iterations)"
                    )
                    return WaitResult(
                        success=True,
                        outcome=WaitOutcome.SUCCESS,
                        element=state,
                        elapsed_ms=elapsed * 1000,
                        iterations=iteration,
                        progress_log=progress_log,
                    )

                # Log current state
                if state is not None:
                    self._log(
                        f"Button '{button_text}' is {state.button_state.value if state.button_state else 'unknown'}, "
                        f"waiting... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                        "debug",
                    )
                else:
                    self._log(
                        f"Button '{button_text}' not found, waiting... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                        "debug",
                    )

            except Exception as e:
                last_error = str(e)
                self._log(f"Error during wait: {e}", "error")

            # Wait before next poll
            time.sleep(interval)

    def wait_for_condition(
        self,
        element_description: str,
        predicate: PredicateFunc,
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
        use_state_detection: bool = True,
    ) -> WaitResult:
        """
        Wait for a custom condition to be met.

        The predicate function receives either a DetectionResult or ElementState
        (depending on use_state_detection) and should return True when the
        condition is satisfied.

        Args:
            element_description: Natural language description of the element.
            predicate: Function that returns True when condition is met.
                       Receives (DetectionResult | ElementState | None) as argument.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds.
            use_state_detection: If True, uses get_element_state() instead of find_element().

        Returns:
            WaitResult with success=True if predicate returns True, False on timeout.

        Example:
            # Wait for progress bar to reach 100%
            def is_complete(state):
                return state and state.progress_value and state.progress_value >= 1.0

            result = wait_for_condition(
                "progress bar",
                predicate=is_complete,
                timeout=120.0,
            )

            # Wait for checkbox to be checked
            def is_checked(state):
                return state and state.checkbox_state == CheckboxState.CHECKED

            result = wait_for_condition(
                "the 'Enable feature' checkbox",
                predicate=is_checked,
                timeout=5.0,
            )
        """
        interval = poll_interval or self._poll_interval

        # Check dependencies
        error = self._check_dependencies()
        if error:
            return WaitResult(
                success=False,
                outcome=WaitOutcome.ERROR,
                last_error=error,
            )

        self._cancel_requested = False
        start_time = time.time()
        iteration = 0
        progress_log: List[WaitProgress] = []
        last_error: Optional[str] = None

        self._log(
            f"Waiting for condition on '{element_description}' (timeout={timeout}s, "
            f"state_detection={use_state_detection})"
        )

        while True:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            # Check for cancellation
            if self._cancel_requested:
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.CANCELLED,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    progress_log=progress_log,
                )

            # Check for timeout
            if elapsed >= timeout:
                self._log(f"Timeout waiting for condition on '{element_description}'", "warning")
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.TIMEOUT,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    last_error=last_error,
                    progress_log=progress_log,
                )

            # Capture screenshot and evaluate condition
            try:
                screenshot = self._capture_screenshot()
                if screenshot is None:
                    last_error = "Failed to capture screenshot"
                    continue

                assert self._detector is not None  # Checked by _check_dependencies
                # Get element/state based on detection mode
                if use_state_detection:
                    result = self._detector.get_element_state(screenshot, element_description)
                else:
                    result = self._detector.find_element(screenshot, element_description)

                # Evaluate predicate
                condition_met = False
                try:
                    condition_met = predicate(result)
                except Exception as pred_err:
                    last_error = f"Predicate error: {pred_err}"
                    self._log(f"Predicate error: {pred_err}", "error")

                progress = WaitProgress(
                    iteration=iteration,
                    elapsed_ms=elapsed * 1000,
                    remaining_ms=remaining * 1000,
                    found=result is not None,
                    element=result,
                    message=f"Condition met: {condition_met}",
                )
                progress_log.append(progress)

                if condition_met:
                    self._log(
                        f"Condition met after {elapsed:.2f}s ({iteration} iterations)"
                    )
                    return WaitResult(
                        success=True,
                        outcome=WaitOutcome.SUCCESS,
                        element=result,
                        elapsed_ms=elapsed * 1000,
                        iterations=iteration,
                        progress_log=progress_log,
                    )

                self._log(
                    f"Condition not met, retrying... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                    "debug",
                )

            except Exception as e:
                last_error = str(e)
                self._log(f"Error during wait: {e}", "error")

            # Wait before next poll
            time.sleep(interval)

    def wait_for_any_element(
        self,
        element_descriptions: List[str],
        timeout: float = DEFAULT_TIMEOUT_S,
        poll_interval: Optional[float] = None,
    ) -> WaitResult:
        """
        Wait for any one of multiple elements to appear.

        Args:
            element_descriptions: List of element descriptions to search for.
            timeout: Maximum time to wait in seconds.
            poll_interval: Polling interval in seconds.

        Returns:
            WaitResult with element set to the first found element.
        """
        interval = poll_interval or self._poll_interval

        # Check dependencies
        error = self._check_dependencies()
        if error:
            return WaitResult(
                success=False,
                outcome=WaitOutcome.ERROR,
                last_error=error,
            )

        self._cancel_requested = False
        start_time = time.time()
        iteration = 0
        progress_log: List[WaitProgress] = []
        last_error: Optional[str] = None

        descriptions_str = ", ".join(f"'{d}'" for d in element_descriptions)
        self._log(f"Waiting for any element: {descriptions_str} (timeout={timeout}s)")

        while True:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            # Check for cancellation
            if self._cancel_requested:
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.CANCELLED,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    progress_log=progress_log,
                )

            # Check for timeout
            if elapsed >= timeout:
                self._log(f"Timeout waiting for any element: {descriptions_str}", "warning")
                return WaitResult(
                    success=False,
                    outcome=WaitOutcome.TIMEOUT,
                    elapsed_ms=elapsed * 1000,
                    iterations=iteration,
                    last_error=last_error,
                    progress_log=progress_log,
                )

            # Capture screenshot
            try:
                screenshot = self._capture_screenshot()
                if screenshot is None:
                    last_error = "Failed to capture screenshot"
                    continue

                assert self._detector is not None  # Checked by _check_dependencies
                # Check each element description
                for desc in element_descriptions:
                    result = self._detector.find_element(screenshot, desc)

                    if result is not None:
                        progress = WaitProgress(
                            iteration=iteration,
                            elapsed_ms=elapsed * 1000,
                            remaining_ms=remaining * 1000,
                            found=True,
                            element=result,
                            message=f"Found: '{desc}'",
                        )
                        progress_log.append(progress)

                        self._log(
                            f"Found '{desc}' after {elapsed:.2f}s ({iteration} iterations)"
                        )
                        return WaitResult(
                            success=True,
                            outcome=WaitOutcome.SUCCESS,
                            element=result,
                            elapsed_ms=elapsed * 1000,
                            iterations=iteration,
                            progress_log=progress_log,
                        )

                progress = WaitProgress(
                    iteration=iteration,
                    elapsed_ms=elapsed * 1000,
                    remaining_ms=remaining * 1000,
                    found=False,
                    message="None found",
                )
                progress_log.append(progress)

                self._log(
                    f"No elements found, retrying... ({iteration}, {elapsed:.1f}s/{timeout}s)",
                    "debug",
                )

            except Exception as e:
                last_error = str(e)
                self._log(f"Error during wait: {e}", "error")

            # Wait before next poll
            time.sleep(interval)


# ============================================================================
# Convenience Functions
# ============================================================================

# Module-level helper instance (lazily created)
_default_helper: Optional[WaitHelper] = None


def _get_default_helper() -> WaitHelper:
    """Get or create the default WaitHelper instance."""
    global _default_helper
    if _default_helper is None:
        _default_helper = WaitHelper()
    return _default_helper


def wait_for_element(
    element_description: str,
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
) -> WaitResult:
    """
    Wait for a UI element to appear.

    Convenience function that uses the default WaitHelper instance.

    Args:
        element_description: Natural language description of the element.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.

    Returns:
        WaitResult with success=True if element found, False on timeout.

    Example:
        result = wait_for_element("the 'Build' button", timeout=10.0)
        if result.success:
            print(f"Button found at ({result.element.x}, {result.element.y})")
    """
    helper = _get_default_helper()
    return helper.wait_for_element(element_description, timeout, poll_interval)


def wait_for_element_gone(
    element_description: str,
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
) -> WaitResult:
    """
    Wait for a UI element to disappear.

    Convenience function that uses the default WaitHelper instance.

    Args:
        element_description: Natural language description of the element.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.

    Returns:
        WaitResult with success=True if element disappeared, False on timeout.

    Example:
        result = wait_for_element_gone("loading spinner", timeout=30.0)
        if result.success:
            print("Loading complete!")
    """
    helper = _get_default_helper()
    return helper.wait_for_element_gone(element_description, timeout, poll_interval)


def wait_for_text(
    text: str,
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
    case_sensitive: bool = True,
) -> WaitResult:
    """
    Wait for specific text to appear in the screenshot.

    Convenience function that uses the default WaitHelper instance.

    Args:
        text: The text to wait for.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.
        case_sensitive: Whether to match case exactly.

    Returns:
        WaitResult with success=True if text found, False on timeout.

    Example:
        result = wait_for_text("Build successful", timeout=60.0)
        if result.success:
            print("Build completed successfully!")
    """
    helper = _get_default_helper()
    return helper.wait_for_text(text, timeout, poll_interval, case_sensitive)


def wait_for_button_enabled(
    button_text: str,
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
) -> WaitResult:
    """
    Wait for a button to become enabled.

    Convenience function that uses the default WaitHelper instance.

    Args:
        button_text: The text on the button.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.

    Returns:
        WaitResult with success=True if button enabled, False on timeout.

    Example:
        result = wait_for_button_enabled("Submit", timeout=15.0)
        if result.success:
            print("Submit button is now clickable!")
    """
    helper = _get_default_helper()
    return helper.wait_for_button_enabled(button_text, timeout, poll_interval)


def wait_for_condition(
    element_description: str,
    predicate: PredicateFunc,
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
    use_state_detection: bool = True,
) -> WaitResult:
    """
    Wait for a custom condition to be met.

    Convenience function that uses the default WaitHelper instance.

    Args:
        element_description: Natural language description of the element.
        predicate: Function that returns True when condition is met.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.
        use_state_detection: If True, uses state detection instead of element finding.

    Returns:
        WaitResult with success=True if predicate returns True, False on timeout.

    Example:
        def is_progress_complete(state):
            return state and state.progress_value and state.progress_value >= 1.0

        result = wait_for_condition(
            "progress bar",
            predicate=is_progress_complete,
            timeout=120.0,
        )
    """
    helper = _get_default_helper()
    return helper.wait_for_condition(
        element_description, predicate, timeout, poll_interval, use_state_detection
    )


def wait_for_any_element(
    element_descriptions: List[str],
    timeout: float = WaitHelper.DEFAULT_TIMEOUT_S,
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
) -> WaitResult:
    """
    Wait for any one of multiple elements to appear.

    Convenience function that uses the default WaitHelper instance.

    Args:
        element_descriptions: List of element descriptions to search for.
        timeout: Maximum time to wait in seconds.
        poll_interval: Polling interval in seconds.

    Returns:
        WaitResult with element set to the first found element.

    Example:
        result = wait_for_any_element(
            ["success message", "error dialog", "warning popup"],
            timeout=30.0,
        )
        if result.success:
            print(f"Found element: {result.element.description}")
    """
    helper = _get_default_helper()
    return helper.wait_for_any_element(element_descriptions, timeout, poll_interval)


def create_wait_helper(
    poll_interval: float = WaitHelper.DEFAULT_POLL_INTERVAL_S,
    min_confidence: float = WaitHelper.DEFAULT_MIN_CONFIDENCE,
    log_progress: bool = True,
) -> WaitHelper:
    """
    Create a new WaitHelper instance with custom configuration.

    Use this when you need custom settings or want to share a helper
    instance across multiple wait operations for caching benefits.

    Args:
        poll_interval: Default polling interval in seconds.
        min_confidence: Minimum confidence threshold for detection.
        log_progress: Whether to log progress during waits.

    Returns:
        Configured WaitHelper instance.

    Example:
        helper = create_wait_helper(poll_interval=0.25, min_confidence=0.8)

        result1 = helper.wait_for_element("button 1")
        result2 = helper.wait_for_element("button 2")  # Benefits from caching
    """
    return WaitHelper(
        poll_interval=poll_interval,
        min_confidence=min_confidence,
        log_progress=log_progress,
    )


# Feature availability flag
WAIT_UTILS_AVAILABLE = VISION_DETECTOR_AVAILABLE and SCREENSHOT_AVAILABLE


__all__ = [
    # Main class
    "WaitHelper",
    # Result types
    "WaitResult",
    "WaitProgress",
    "WaitOutcome",
    # Type aliases
    "PredicateFunc",
    # Convenience functions
    "wait_for_element",
    "wait_for_element_gone",
    "wait_for_text",
    "wait_for_button_enabled",
    "wait_for_condition",
    "wait_for_any_element",
    "create_wait_helper",
    # Availability flag
    "WAIT_UTILS_AVAILABLE",
]
