#!/usr/bin/env python3
"""
unity_panels.py - Unity Editor Panel Detection and Interaction

This module provides detection and interaction capabilities for Unity Editor panels
using vision-based detection. It enables:
- Detecting if specific Unity panels are open/visible
- Getting panel locations and bounds
- Finding buttons within panels
- Clicking buttons within specific panels
- Waiting for panels to appear

Usage:
    from agents.computer_use.unity_panels import UnityPanelDetector

    detector = UnityPanelDetector()

    # Check if a panel is open
    if detector.is_panel_open("Building Blocks"):
        print("Building Blocks panel is visible")

    # Get panel bounds
    bounds = detector.get_panel_bounds("Console")
    if bounds:
        print(f"Console panel at ({bounds.x}, {bounds.y})")

    # Click a button within a panel
    result = detector.click_button_in_panel("Project Setup Tool", "Fix All")
    if result.success:
        print("Clicked Fix All button")
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

# Set up logging
logger = logging.getLogger(__name__)


class PanelType(Enum):
    """Types of Unity Editor panels."""
    BUILDING_BLOCKS = "Building Blocks"
    PROJECT_SETUP_TOOL = "Project Setup Tool"
    INSPECTOR = "Inspector"
    HIERARCHY = "Hierarchy"
    CONSOLE = "Console"
    PROJECT = "Project"
    SCENE = "Scene"
    GAME = "Game"
    ANIMATION = "Animation"
    ANIMATOR = "Animator"
    PROFILER = "Profiler"
    ASSET_STORE = "Asset Store"
    PACKAGE_MANAGER = "Package Manager"
    BUILD_SETTINGS = "Build Settings"
    PREFERENCES = "Preferences"
    CUSTOM = "Custom"


class PanelLayout(Enum):
    """How a panel is displayed in Unity."""
    DOCKED = "docked"
    FLOATING = "floating"
    TAB = "tab"  # Docked as a tab with other panels
    UNKNOWN = "unknown"


@dataclass
class PanelBounds:
    """Bounding box for a Unity panel."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    layout: PanelLayout = PanelLayout.UNKNOWN

    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates of the panel."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
            "confidence": self.confidence,
            "layout": self.layout.value,
        }

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within this panel's bounds."""
        return (self.x <= x < self.x + self.width and
                self.y <= y < self.y + self.height)


@dataclass
class PanelDetectionResult:
    """Result of panel detection."""
    found: bool
    panel_name: str
    bounds: Optional[PanelBounds] = None
    layout: PanelLayout = PanelLayout.UNKNOWN
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "found": self.found,
            "panel_name": self.panel_name,
            "layout": self.layout.value,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "cached": self.cached,
        }
        if self.bounds:
            result["bounds"] = self.bounds.to_dict()
        return result


@dataclass
class ButtonInPanelResult:
    """Result of finding a button within a panel."""
    found: bool
    button_name: str
    panel_name: str
    x: Optional[int] = None
    y: Optional[int] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "found": self.found,
            "button_name": self.button_name,
            "panel_name": self.panel_name,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "error_message": self.error_message,
        }


@dataclass
class ClickInPanelResult:
    """Result of clicking a button within a panel."""
    success: bool
    button_name: str
    panel_name: str
    x: Optional[int] = None
    y: Optional[int] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    panel_bounds: Optional[PanelBounds] = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "button_name": self.button_name,
            "panel_name": self.panel_name,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.panel_bounds:
            result["panel_bounds"] = self.panel_bounds.to_dict()
        return result


# Import availability flags
VISION_DETECTOR_AVAILABLE = False
CLICK_HANDLER_AVAILABLE = False
SCREENSHOT_AVAILABLE = False

try:
    from .vision_detector import VisionDetector
    VISION_DETECTOR_AVAILABLE = True
except ImportError:
    VisionDetector = None  # type: ignore

try:
    from .click_handler import ClickHandler
    CLICK_HANDLER_AVAILABLE = True
except ImportError:
    ClickHandler = None  # type: ignore

try:
    from .screenshot import MultiMonitorCapture
    SCREENSHOT_AVAILABLE = True
except ImportError:
    MultiMonitorCapture = None  # type: ignore


@dataclass
class CachedPanelLocation:
    """Cached panel location with TTL."""
    bounds: PanelBounds
    timestamp: datetime
    ttl_seconds: float


class UnityPanelDetector:
    """
    Unity Editor panel detection and interaction using vision-based detection.

    This class provides:
    - Panel detection using Claude Vision API
    - Support for common Unity panels (Building Blocks, Project Setup Tool, etc.)
    - Panel location caching for efficiency
    - Button finding within specific panels
    - Click operations within panels
    - Wait utilities for panel appearance

    Supported Panels:
    - Building Blocks: Meta XR building blocks panel
    - Project Setup Tool: Unity project setup and configuration
    - Inspector: Unity Inspector panel
    - Hierarchy: Scene hierarchy panel
    - Console: Debug console panel
    - Project: Project browser panel
    - Scene/Game: Scene and Game view panels

    Example:
        detector = UnityPanelDetector()

        # Check if panel is visible
        if detector.is_panel_open("Building Blocks"):
            # Get panel location
            bounds = detector.get_panel_bounds("Building Blocks")

            # Find a button within the panel
            button = detector.find_button_in_panel("Building Blocks", "Add")

            # Click the button
            result = detector.click_button_in_panel("Building Blocks", "Add")
    """

    # Default timing constants
    DEFAULT_POLL_INTERVAL = 0.5  # seconds
    DEFAULT_TIMEOUT = 10.0  # seconds
    DEFAULT_CACHE_TTL = 30.0  # seconds
    DEFAULT_MIN_CONFIDENCE = 0.7

    # Panel name aliases for more flexible matching
    PANEL_ALIASES: Dict[str, List[str]] = {
        "Building Blocks": ["Building Blocks", "Meta Building Blocks", "XR Building Blocks"],
        "Project Setup Tool": ["Project Setup Tool", "Project Setup", "Setup Tool"],
        "Inspector": ["Inspector"],
        "Hierarchy": ["Hierarchy"],
        "Console": ["Console"],
        "Project": ["Project"],
        "Scene": ["Scene"],
        "Game": ["Game"],
        "Animation": ["Animation"],
        "Animator": ["Animator"],
        "Profiler": ["Profiler"],
        "Package Manager": ["Package Manager"],
        "Build Settings": ["Build Settings"],
    }

    def __init__(
        self,
        vision_detector: Optional[Any] = None,
        click_handler: Optional[Any] = None,
        screenshot_capture: Optional[Any] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        enable_caching: bool = True,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ):
        """
        Initialize the UnityPanelDetector.

        Args:
            vision_detector: VisionDetector instance. If None, creates one when needed.
            click_handler: ClickHandler instance. If None, creates one when needed.
            screenshot_capture: MultiMonitorCapture instance. If None, creates one when needed.
            min_confidence: Minimum confidence threshold for detection.
            enable_caching: Whether to cache panel locations.
            cache_ttl: Cache time-to-live in seconds.
        """
        self._vision_detector = vision_detector
        self._click_handler = click_handler
        self._screenshot_capture = screenshot_capture
        self._min_confidence = min_confidence
        self._enable_caching = enable_caching
        self._cache_ttl = cache_ttl

        # Panel location cache
        self._panel_cache: Dict[str, CachedPanelLocation] = {}

        # Lazy initialization flags
        self._vision_initialized = False
        self._click_initialized = False
        self._screenshot_initialized = False

    def _get_vision_detector(self) -> Optional[Any]:
        """Get or create the VisionDetector instance."""
        if not VISION_DETECTOR_AVAILABLE:
            logger.warning("VisionDetector not available - anthropic package not installed")
            return None

        if self._vision_detector is None and not self._vision_initialized:
            try:
                self._vision_detector = VisionDetector(  # type: ignore[misc]
                    min_confidence=self._min_confidence
                )
                self._vision_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize VisionDetector: {e}")
                self._vision_initialized = True  # Don't retry

        return self._vision_detector

    def _get_click_handler(self) -> Optional[Any]:
        """Get or create the ClickHandler instance."""
        if not CLICK_HANDLER_AVAILABLE:
            logger.warning("ClickHandler not available")
            return None

        if self._click_handler is None and not self._click_initialized:
            try:
                self._click_handler = ClickHandler(  # type: ignore[misc]
                    min_confidence=self._min_confidence
                )
                self._click_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize ClickHandler: {e}")
                self._click_initialized = True  # Don't retry

        return self._click_handler

    def _get_screenshot_capture(self) -> Optional[Any]:
        """Get or create the MultiMonitorCapture instance."""
        if not SCREENSHOT_AVAILABLE:
            logger.warning("Screenshot capture not available - Quartz/PIL not installed")
            return None

        if self._screenshot_capture is None and not self._screenshot_initialized:
            try:
                self._screenshot_capture = MultiMonitorCapture()  # type: ignore[misc]
                self._screenshot_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize MultiMonitorCapture: {e}")
                self._screenshot_initialized = True  # Don't retry

        return self._screenshot_capture

    def _get_cached_panel(self, panel_name: str) -> Optional[PanelBounds]:
        """Get cached panel location if still valid."""
        if not self._enable_caching:
            return None

        normalized_name = self._normalize_panel_name(panel_name)
        cached = self._panel_cache.get(normalized_name)

        if cached is None:
            return None

        # Check if cache is still valid
        age = (datetime.now() - cached.timestamp).total_seconds()
        if age > cached.ttl_seconds:
            del self._panel_cache[normalized_name]
            return None

        return cached.bounds

    def _cache_panel_location(self, panel_name: str, bounds: PanelBounds) -> None:
        """Cache a panel's location."""
        if not self._enable_caching:
            return

        normalized_name = self._normalize_panel_name(panel_name)
        self._panel_cache[normalized_name] = CachedPanelLocation(
            bounds=bounds,
            timestamp=datetime.now(),
            ttl_seconds=self._cache_ttl,
        )

    def _normalize_panel_name(self, panel_name: str) -> str:
        """Normalize panel name for consistent lookup."""
        # Check if it matches any known panel aliases
        lower_name = panel_name.lower().strip()
        for canonical_name, aliases in self.PANEL_ALIASES.items():
            for alias in aliases:
                if alias.lower() == lower_name:
                    return canonical_name
        return panel_name.strip()

    def _capture_screenshot(self) -> Optional[bytes]:
        """Capture a screenshot for panel detection."""
        capture = self._get_screenshot_capture()
        if capture is None:
            return None

        try:
            result = capture.capture_all_displays()
            return result.image_bytes
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")
            return None

    def _build_panel_search_query(self, panel_name: str) -> str:
        """Build a vision API search query for a panel."""
        normalized = self._normalize_panel_name(panel_name)

        # Unity-specific search queries for better accuracy
        queries = {
            "Building Blocks": (
                "the Unity Editor panel titled 'Building Blocks' or 'Meta Building Blocks' "
                "which shows a list of XR building blocks that can be added to the project"
            ),
            "Project Setup Tool": (
                "the Unity Editor panel titled 'Project Setup Tool' showing project setup "
                "configuration with options like 'Fix All' and 'Apply All'"
            ),
            "Inspector": (
                "the Unity Editor Inspector panel showing properties of the selected object"
            ),
            "Hierarchy": (
                "the Unity Editor Hierarchy panel showing the scene hierarchy tree"
            ),
            "Console": (
                "the Unity Editor Console panel showing log messages, warnings, and errors"
            ),
            "Project": (
                "the Unity Editor Project panel showing the project file browser"
            ),
            "Scene": (
                "the Unity Editor Scene view panel showing the 3D scene"
            ),
            "Game": (
                "the Unity Editor Game view panel showing the game preview"
            ),
            "Package Manager": (
                "the Unity Package Manager window showing available and installed packages"
            ),
            "Build Settings": (
                "the Unity Build Settings window showing platform and build options"
            ),
        }

        return queries.get(normalized, f"the Unity Editor panel titled '{panel_name}'")

    def is_panel_open(self, panel_name: str) -> bool:
        """
        Check if a Unity panel is open and visible.

        Args:
            panel_name: Name of the panel (e.g., "Building Blocks", "Console").

        Returns:
            True if the panel is found and visible, False otherwise.
        """
        result = self.get_panel_bounds(panel_name)
        return result is not None

    def get_panel_bounds(
        self,
        panel_name: str,
        use_cache: bool = True,
    ) -> Optional[PanelBounds]:
        """
        Get the bounding box of a Unity panel.

        Args:
            panel_name: Name of the panel to find.
            use_cache: Whether to use cached location if available.

        Returns:
            PanelBounds if found, None otherwise.
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_panel(panel_name)
            if cached is not None:
                logger.debug(f"Using cached location for panel '{panel_name}'")
                return cached

        # Need to use vision detection
        vision = self._get_vision_detector()
        if vision is None:
            logger.error("Cannot detect panel - VisionDetector not available")
            return None

        screenshot = self._capture_screenshot()
        if screenshot is None:
            logger.error("Cannot detect panel - failed to capture screenshot")
            return None

        # Search for the panel
        search_query = self._build_panel_search_query(panel_name)
        logger.debug(f"Searching for panel '{panel_name}' with query: {search_query}")

        try:
            detection = vision.find_element(screenshot, search_query)
        except Exception as e:
            logger.error(f"Vision API error while searching for panel '{panel_name}': {e}")
            return None

        if detection is None:
            logger.debug(f"Panel '{panel_name}' not found in screenshot")
            return None

        if detection.confidence < self._min_confidence:
            logger.debug(
                f"Panel '{panel_name}' found but confidence {detection.confidence:.2f} "
                f"below threshold {self._min_confidence}"
            )
            return None

        # Build panel bounds
        if detection.bounding_box:
            bounds = PanelBounds(
                x=detection.bounding_box.x,
                y=detection.bounding_box.y,
                width=detection.bounding_box.width,
                height=detection.bounding_box.height,
                confidence=detection.confidence,
                layout=PanelLayout.UNKNOWN,  # Could enhance to detect layout
            )
        else:
            # No bounding box, estimate from center point
            # Use a reasonable default size for panels
            estimated_width = 300
            estimated_height = 400
            bounds = PanelBounds(
                x=detection.x - estimated_width // 2,
                y=detection.y - estimated_height // 2,
                width=estimated_width,
                height=estimated_height,
                confidence=detection.confidence,
                layout=PanelLayout.UNKNOWN,
            )

        # Cache the result
        self._cache_panel_location(panel_name, bounds)

        logger.debug(
            f"Found panel '{panel_name}' at ({bounds.x}, {bounds.y}) "
            f"size {bounds.width}x{bounds.height} confidence {bounds.confidence:.2f}"
        )

        return bounds

    def wait_for_panel(
        self,
        panel_name: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Optional[PanelBounds]:
        """
        Wait for a Unity panel to appear.

        Polls for the panel at regular intervals until it appears or timeout.

        Args:
            panel_name: Name of the panel to wait for.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between polling attempts in seconds.

        Returns:
            PanelBounds if found within timeout, None otherwise.

        Raises:
            TimeoutError: If panel doesn't appear within timeout (optional).
        """
        start_time = time.time()
        attempts = 0

        logger.info(f"Waiting for panel '{panel_name}' (timeout: {timeout}s)")

        while time.time() - start_time < timeout:
            attempts += 1
            logger.debug(f"Checking for panel '{panel_name}' (attempt {attempts})")

            # Don't use cache for wait operations
            bounds = self.get_panel_bounds(panel_name, use_cache=False)

            if bounds is not None:
                logger.info(
                    f"Panel '{panel_name}' appeared after {attempts} attempts "
                    f"({time.time() - start_time:.1f}s)"
                )
                return bounds

            time.sleep(poll_interval)

        logger.warning(
            f"Panel '{panel_name}' did not appear within {timeout}s ({attempts} attempts)"
        )
        return None

    def find_button_in_panel(
        self,
        panel_name: str,
        button_text: str,
    ) -> ButtonInPanelResult:
        """
        Find a button within a specific Unity panel.

        Args:
            panel_name: Name of the panel to search within.
            button_text: Text label of the button to find.

        Returns:
            ButtonInPanelResult with button location if found.
        """
        result = ButtonInPanelResult(
            found=False,
            button_name=button_text,
            panel_name=panel_name,
        )

        # First, verify the panel is visible and get its bounds
        panel_bounds = self.get_panel_bounds(panel_name)
        if panel_bounds is None:
            result.error_message = f"Panel '{panel_name}' not found"
            return result

        # Now search for the button within the panel context
        vision = self._get_vision_detector()
        if vision is None:
            result.error_message = "VisionDetector not available"
            return result

        screenshot = self._capture_screenshot()
        if screenshot is None:
            result.error_message = "Failed to capture screenshot"
            return result

        # Build a specific query for the button within the panel
        search_query = (
            f"the button labeled '{button_text}' within the '{panel_name}' panel "
            f"in the Unity Editor"
        )

        try:
            detection = vision.find_element(screenshot, search_query)
        except Exception as e:
            result.error_message = f"Vision API error: {e}"
            return result

        if detection is None:
            result.error_message = f"Button '{button_text}' not found in panel '{panel_name}'"
            return result

        if detection.confidence < self._min_confidence:
            result.error_message = (
                f"Button found but confidence {detection.confidence:.2f} "
                f"below threshold {self._min_confidence}"
            )
            result.confidence = detection.confidence
            return result

        # Verify the button is within the panel bounds
        if not panel_bounds.contains_point(detection.x, detection.y):
            # The button might be found but outside the panel - this is a warning
            logger.warning(
                f"Button '{button_text}' found at ({detection.x}, {detection.y}) "
                f"but appears to be outside panel bounds"
            )

        result.found = True
        result.x = detection.x
        result.y = detection.y
        result.confidence = detection.confidence

        logger.debug(
            f"Found button '{button_text}' in panel '{panel_name}' "
            f"at ({detection.x}, {detection.y}) confidence {detection.confidence:.2f}"
        )

        return result

    def click_button_in_panel(
        self,
        panel_name: str,
        button_text: str,
        verify_panel_first: bool = True,
    ) -> ClickInPanelResult:
        """
        Click a button within a specific Unity panel.

        Args:
            panel_name: Name of the panel containing the button.
            button_text: Text label of the button to click.
            verify_panel_first: If True, verify panel exists before clicking.

        Returns:
            ClickInPanelResult with click details.
        """
        start_time = time.time()

        result = ClickInPanelResult(
            success=False,
            button_name=button_text,
            panel_name=panel_name,
        )

        # Verify panel is visible if requested
        panel_bounds = None
        if verify_panel_first:
            panel_bounds = self.get_panel_bounds(panel_name)
            if panel_bounds is None:
                result.error_message = f"Panel '{panel_name}' not found"
                result.duration_ms = int((time.time() - start_time) * 1000)
                return result
            result.panel_bounds = panel_bounds

        # Find the button first
        button_result = self.find_button_in_panel(panel_name, button_text)
        if not button_result.found:
            result.error_message = button_result.error_message
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        result.x = button_result.x
        result.y = button_result.y
        result.confidence = button_result.confidence

        # Use click handler to click at the button coordinates
        click_handler = self._get_click_handler()
        if click_handler is None:
            result.error_message = "ClickHandler not available"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        # Click using vision_only mode since we already found the coordinates
        try:
            click_result = click_handler.click_element(
                app_name="Unity",
                element_name=button_text,
                vision_only=True,  # Skip AppleScript since we have coordinates
            )
        except Exception as e:
            result.error_message = f"Click operation failed: {e}"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        if click_result.success:
            result.success = True
            logger.info(
                f"Clicked button '{button_text}' in panel '{panel_name}' "
                f"at ({result.x}, {result.y})"
            )
        else:
            result.error_message = f"Click failed: {click_result.error_message}"
            logger.warning(
                f"Failed to click button '{button_text}' in panel '{panel_name}': "
                f"{click_result.error_message}"
            )

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def invalidate_cache(self, panel_name: Optional[str] = None) -> None:
        """
        Invalidate cached panel locations.

        Args:
            panel_name: Specific panel to invalidate. If None, clears all cache.
        """
        if panel_name is None:
            self._panel_cache.clear()
            logger.debug("Cleared all panel cache")
        else:
            normalized = self._normalize_panel_name(panel_name)
            if normalized in self._panel_cache:
                del self._panel_cache[normalized]
                logger.debug(f"Invalidated cache for panel '{panel_name}'")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now()
        valid_entries = 0
        expired_entries = 0

        for cached in self._panel_cache.values():
            age = (now - cached.timestamp).total_seconds()
            if age <= cached.ttl_seconds:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "total_entries": len(self._panel_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "caching_enabled": self._enable_caching,
            "cache_ttl_seconds": self._cache_ttl,
        }

    def set_min_confidence(self, threshold: float) -> None:
        """
        Set the minimum confidence threshold.

        Args:
            threshold: Value between 0.0 and 1.0.
        """
        self._min_confidence = threshold
        if self._vision_detector is not None:
            self._vision_detector.set_min_confidence(threshold)

    def set_cache_ttl(self, ttl_seconds: float) -> None:
        """
        Set the cache time-to-live.

        Args:
            ttl_seconds: Cache TTL in seconds.
        """
        self._cache_ttl = ttl_seconds


# Convenience functions

def is_panel_open(panel_name: str, min_confidence: float = 0.7) -> bool:
    """
    Check if a Unity panel is open.

    Convenience function that creates a detector instance and checks
    for the panel.

    Args:
        panel_name: Name of the panel to check.
        min_confidence: Minimum confidence threshold.

    Returns:
        True if panel is found, False otherwise.
    """
    detector = UnityPanelDetector(min_confidence=min_confidence)
    return detector.is_panel_open(panel_name)


def get_panel_bounds(
    panel_name: str,
    min_confidence: float = 0.7,
) -> Optional[PanelBounds]:
    """
    Get the bounds of a Unity panel.

    Convenience function that creates a detector instance and finds
    the panel bounds.

    Args:
        panel_name: Name of the panel to find.
        min_confidence: Minimum confidence threshold.

    Returns:
        PanelBounds if found, None otherwise.
    """
    detector = UnityPanelDetector(min_confidence=min_confidence)
    return detector.get_panel_bounds(panel_name)


def wait_for_panel(
    panel_name: str,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    min_confidence: float = 0.7,
) -> Optional[PanelBounds]:
    """
    Wait for a Unity panel to appear.

    Convenience function that creates a detector instance and waits
    for the panel.

    Args:
        panel_name: Name of the panel to wait for.
        timeout: Maximum time to wait in seconds.
        poll_interval: Time between polls in seconds.
        min_confidence: Minimum confidence threshold.

    Returns:
        PanelBounds if found within timeout, None otherwise.
    """
    detector = UnityPanelDetector(min_confidence=min_confidence)
    return detector.wait_for_panel(panel_name, timeout, poll_interval)


def click_button_in_panel(
    panel_name: str,
    button_text: str,
    min_confidence: float = 0.7,
) -> ClickInPanelResult:
    """
    Click a button within a Unity panel.

    Convenience function that creates a detector instance and clicks
    the button.

    Args:
        panel_name: Name of the panel containing the button.
        button_text: Text label of the button to click.
        min_confidence: Minimum confidence threshold.

    Returns:
        ClickInPanelResult with click details.
    """
    detector = UnityPanelDetector(min_confidence=min_confidence)
    return detector.click_button_in_panel(panel_name, button_text)


# Availability flag
UNITY_PANELS_AVAILABLE = VISION_DETECTOR_AVAILABLE and SCREENSHOT_AVAILABLE


__all__ = [
    # Main class
    "UnityPanelDetector",
    # Enums
    "PanelType",
    "PanelLayout",
    # Data classes
    "PanelBounds",
    "PanelDetectionResult",
    "ButtonInPanelResult",
    "ClickInPanelResult",
    # Convenience functions
    "is_panel_open",
    "get_panel_bounds",
    "wait_for_panel",
    "click_button_in_panel",
    # Availability flag
    "UNITY_PANELS_AVAILABLE",
]
