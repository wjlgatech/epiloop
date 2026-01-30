#!/usr/bin/env python3
"""
screenshot.py - Multi-monitor screenshot capture for macOS

This module provides comprehensive screenshot capture capabilities
across multiple monitors on macOS, using the Quartz (Core Graphics) framework.
Supports Retina displays and returns coordinates in the combined display space.

Usage:
    from agents.computer_use.screenshot import MultiMonitorCapture

    capture = MultiMonitorCapture()
    screenshot, display_info = capture.capture_all_displays()

    # Get coordinates relative to the combined display space
    global_coords = capture.get_global_coordinates(display_id, local_x, local_y)
"""

import io
import os
import base64
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Union

# Platform-specific imports with fallbacks
try:
    import Quartz
    from Quartz import (
        CGGetActiveDisplayList,
        CGDisplayBounds,
        CGDisplayCreateImage,
        CGMainDisplayID,
        CGDisplayScreenSize,
        CGDisplayPixelsHigh,
        CGDisplayPixelsWide,
        CGRectGetWidth,
        CGRectGetHeight,
        CGRectGetMinX,
        CGRectGetMinY,
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
    )
    from Quartz.CoreGraphics import (
        CGImageGetWidth,
        CGImageGetHeight,
        CGImageGetBytesPerRow,
        CGImageGetDataProvider,
        CGDataProviderCopyData,
        CGWindowListCreateImage,
        CGRectNull,
        kCGWindowImageDefault,
        kCGWindowImageBoundsIgnoreFraming,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

# AppKit for NSWorkspace (window enumeration)
try:
    from AppKit import NSWorkspace
    APPKIT_AVAILABLE = True
except ImportError:
    APPKIT_AVAILABLE = False

# Default screenshot storage location
DEFAULT_SCREENSHOT_DIR = Path(".claude-loop/screenshots")

# PIL/Pillow for image stitching
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class DisplayArrangement(Enum):
    """How displays are arranged relative to primary."""
    LEFT = "left"
    RIGHT = "right"
    ABOVE = "above"
    BELOW = "below"
    PRIMARY = "primary"


@dataclass
class DisplayInfo:
    """Information about a connected display."""
    display_id: int
    bounds: 'DisplayBounds'
    is_primary: bool = False
    is_retina: bool = False
    scale_factor: float = 1.0
    physical_size_mm: Optional[Tuple[float, float]] = None  # width, height in mm
    arrangement: DisplayArrangement = DisplayArrangement.PRIMARY

    def __repr__(self) -> str:
        retina_str = " (Retina)" if self.is_retina else ""
        return (f"Display({self.display_id}: {self.bounds.width}x{self.bounds.height} "
                f"at ({self.bounds.x}, {self.bounds.y}){retina_str})")


@dataclass
class DisplayBounds:
    """Bounds of a display in global coordinate space."""
    x: float  # X position in global coords (can be negative)
    y: float  # Y position in global coords (can be negative for displays above)
    width: float  # Width in points
    height: float  # Height in points
    pixel_width: int = 0  # Actual pixel width (for Retina)
    pixel_height: int = 0  # Actual pixel height (for Retina)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is within this display's bounds."""
        return (self.x <= x < self.x + self.width and
                self.y <= y < self.y + self.height)

    def to_local(self, global_x: float, global_y: float) -> Tuple[float, float]:
        """Convert global coordinates to local display coordinates."""
        return (global_x - self.x, global_y - self.y)

    def to_global(self, local_x: float, local_y: float) -> Tuple[float, float]:
        """Convert local display coordinates to global coordinates."""
        return (local_x + self.x, local_y + self.y)


@dataclass
class CombinedDisplaySpace:
    """Represents the combined coordinate space of all displays."""
    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0
    total_width: float = 0.0
    total_height: float = 0.0
    displays: List[DisplayInfo] = field(default_factory=list)

    @classmethod
    def from_displays(cls, displays: List[DisplayInfo]) -> 'CombinedDisplaySpace':
        """Create combined space from a list of displays."""
        if not displays:
            return cls()

        min_x = min(d.bounds.x for d in displays)
        min_y = min(d.bounds.y for d in displays)
        max_x = max(d.bounds.x + d.bounds.width for d in displays)
        max_y = max(d.bounds.y + d.bounds.height for d in displays)

        return cls(
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
            total_width=max_x - min_x,
            total_height=max_y - min_y,
            displays=displays
        )

    def normalize_coordinates(self, x: float, y: float) -> Tuple[float, float]:
        """Convert global coordinates to normalized (0-based) coordinates for the stitched image."""
        return (x - self.min_x, y - self.min_y)

    def denormalize_coordinates(self, norm_x: float, norm_y: float) -> Tuple[float, float]:
        """Convert normalized coordinates back to global screen coordinates."""
        return (norm_x + self.min_x, norm_y + self.min_y)


@dataclass
class WindowInfo:
    """Information about an application window."""
    window_id: int
    app_name: str
    window_title: str
    bounds: DisplayBounds
    display_id: Optional[int] = None
    is_on_screen: bool = True
    layer: int = 0

    def __repr__(self) -> str:
        return (f"Window({self.app_name}: '{self.window_title}' "
                f"{int(self.bounds.width)}x{int(self.bounds.height)} "
                f"at ({int(self.bounds.x)}, {int(self.bounds.y)}))")


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture operation."""
    image_bytes: bytes
    width: int
    height: int
    format: str = "PNG"
    combined_space: Optional[CombinedDisplaySpace] = None
    display_info: Optional[List[DisplayInfo]] = None
    scale_factor: float = 1.0  # For Retina displays
    window_info: Optional[WindowInfo] = None  # If captured from a window
    timestamp: Optional[datetime] = None
    saved_path: Optional[Path] = None  # Path where screenshot was saved

    def to_base64(self) -> str:
        """
        Convert screenshot to base64 string for API transmission.

        Returns:
            Base64-encoded string of the image bytes.
        """
        return base64.b64encode(self.image_bytes).decode('utf-8')

    def to_data_uri(self) -> str:
        """
        Convert screenshot to a data URI for embedding in HTML or API payloads.

        Returns:
            Data URI string (e.g., "data:image/png;base64,...")
        """
        b64 = self.to_base64()
        return f"data:image/{self.format.lower()};base64,{b64}"

    def save(
        self,
        directory: Optional[Union[str, Path]] = None,
        filename: Optional[str] = None,
        include_timestamp: bool = True
    ) -> Path:
        """
        Save screenshot to disk.

        Args:
            directory: Directory to save to. Defaults to .claude-loop/screenshots/
            filename: Custom filename. If not provided, auto-generates with timestamp.
            include_timestamp: Include timestamp in auto-generated filename.

        Returns:
            Path to the saved file.
        """
        if directory is None:
            directory = DEFAULT_SCREENSHOT_DIR
        else:
            directory = Path(directory)

        # Ensure directory exists
        directory.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if filename is None:
            if include_timestamp:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"screenshot_{ts}.{self.format.lower()}"
            else:
                filename = f"screenshot.{self.format.lower()}"

        filepath = directory / filename
        filepath.write_bytes(self.image_bytes)
        self.saved_path = filepath

        return filepath


class MultiMonitorCapture:
    """
    Captures screenshots from all connected monitors on macOS.

    This class provides:
    - Enumeration of all connected displays
    - Individual display capture
    - Stitched panoramic capture of all displays
    - Coordinate mapping between displays
    - Retina display support with proper scaling
    """

    def __init__(self, enable_retina_scaling: bool = True):
        """
        Initialize the multi-monitor capture.

        Args:
            enable_retina_scaling: If True, capture at native resolution for Retina displays.
                                  If False, capture at logical resolution.
        """
        self._enable_retina_scaling = enable_retina_scaling
        self._display_cache: Optional[List[DisplayInfo]] = None
        self._combined_space: Optional[CombinedDisplaySpace] = None

        if not QUARTZ_AVAILABLE:
            raise RuntimeError(
                "Quartz framework not available. This module requires macOS with "
                "pyobjc-framework-Quartz installed. Install with: "
                "pip install pyobjc-framework-Quartz"
            )

        if not PIL_AVAILABLE:
            raise RuntimeError(
                "PIL/Pillow not available. This module requires Pillow for image "
                "stitching. Install with: pip install Pillow"
            )

    def get_displays(self, force_refresh: bool = False) -> List[DisplayInfo]:
        """
        Get information about all connected displays.

        Args:
            force_refresh: If True, re-enumerate displays even if cached.

        Returns:
            List of DisplayInfo objects for each connected display.
        """
        if self._display_cache is not None and not force_refresh:
            return self._display_cache

        # Get number of displays
        err, display_ids, display_count = CGGetActiveDisplayList(32, None, None)
        if err != 0:
            raise RuntimeError(f"Failed to get display list: error {err}")

        main_display_id = CGMainDisplayID()
        displays = []

        for i in range(display_count):
            display_id = display_ids[i]
            bounds_rect = CGDisplayBounds(display_id)

            # Get bounds in points (logical coordinates)
            x = CGRectGetMinX(bounds_rect)
            y = CGRectGetMinY(bounds_rect)
            width = CGRectGetWidth(bounds_rect)
            height = CGRectGetHeight(bounds_rect)

            # Get pixel dimensions (for Retina)
            pixel_width = CGDisplayPixelsWide(display_id)
            pixel_height = CGDisplayPixelsHigh(display_id)

            # Calculate scale factor
            scale_factor = pixel_width / width if width > 0 else 1.0
            is_retina = scale_factor > 1.0

            # Determine arrangement relative to primary
            is_primary = (display_id == main_display_id)
            if is_primary:
                arrangement = DisplayArrangement.PRIMARY
            elif x < 0:
                arrangement = DisplayArrangement.LEFT
            elif x > 0:
                arrangement = DisplayArrangement.RIGHT
            elif y < 0:
                arrangement = DisplayArrangement.ABOVE
            else:
                arrangement = DisplayArrangement.BELOW

            # Get physical size (if available)
            physical_size = None
            try:
                size = CGDisplayScreenSize(display_id)
                if size.width > 0 and size.height > 0:
                    physical_size = (size.width, size.height)
            except Exception:
                pass

            display_info = DisplayInfo(
                display_id=display_id,
                bounds=DisplayBounds(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    pixel_width=pixel_width,
                    pixel_height=pixel_height
                ),
                is_primary=is_primary,
                is_retina=is_retina,
                scale_factor=scale_factor,
                physical_size_mm=physical_size,
                arrangement=arrangement
            )
            displays.append(display_info)

        # Sort displays: primary first, then left-to-right, top-to-bottom
        displays.sort(key=lambda d: (
            not d.is_primary,
            d.bounds.y,
            d.bounds.x
        ))

        self._display_cache = displays
        self._combined_space = CombinedDisplaySpace.from_displays(displays)

        return displays

    def get_combined_space(self) -> CombinedDisplaySpace:
        """Get the combined display space information."""
        if self._combined_space is None:
            self.get_displays()
        return self._combined_space  # type: ignore

    def capture_display(self, display_id: Optional[int] = None) -> ScreenshotResult:
        """
        Capture screenshot from a single display.

        Args:
            display_id: The display ID to capture. If None, captures primary display.

        Returns:
            ScreenshotResult containing the captured image.
        """
        if display_id is None:
            display_id = CGMainDisplayID()

        # Create image of the display
        image_ref = CGDisplayCreateImage(display_id)
        if image_ref is None:
            raise RuntimeError(f"Failed to capture display {display_id}")

        # Get image dimensions
        width = CGImageGetWidth(image_ref)
        height = CGImageGetHeight(image_ref)

        # Convert CGImage to bytes
        image_bytes = self._cgimage_to_bytes(image_ref, width, height)

        # Find display info
        displays = self.get_displays()
        display_info = next((d for d in displays if d.display_id == display_id), None)
        scale_factor = display_info.scale_factor if display_info else 1.0

        return ScreenshotResult(
            image_bytes=image_bytes,
            width=width,
            height=height,
            format="PNG",
            scale_factor=scale_factor,
            display_info=[display_info] if display_info else None
        )

    def capture_all_displays(self) -> ScreenshotResult:
        """
        Capture screenshots from all displays and stitch into a single image.

        Returns:
            ScreenshotResult containing the stitched panoramic screenshot
            and combined display space information.
        """
        displays = self.get_displays(force_refresh=True)
        combined_space = self.get_combined_space()

        if not displays:
            raise RuntimeError("No displays found")

        # If single display, just capture it directly
        if len(displays) == 1:
            result = self.capture_display(displays[0].display_id)
            result.combined_space = combined_space
            result.display_info = displays
            return result

        # Calculate the canvas size needed for stitching
        # Use native pixel resolution for the canvas
        max_scale = max(d.scale_factor for d in displays)
        canvas_width = int(combined_space.total_width * max_scale)
        canvas_height = int(combined_space.total_height * max_scale)

        # Create canvas for stitching
        canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 255))

        # Capture and place each display
        for display in displays:
            image_ref = CGDisplayCreateImage(display.display_id)
            if image_ref is None:
                continue

            width = CGImageGetWidth(image_ref)
            height = CGImageGetHeight(image_ref)

            # Convert to PIL Image
            image_bytes = self._cgimage_to_bytes(image_ref, width, height)
            display_image = Image.open(io.BytesIO(image_bytes))

            # Calculate position in canvas (normalized to 0-based coordinates)
            norm_x, norm_y = combined_space.normalize_coordinates(
                display.bounds.x, display.bounds.y
            )

            # Scale position to pixel coordinates
            paste_x = int(norm_x * max_scale)
            paste_y = int(norm_y * max_scale)

            # Resize image if scale factors don't match
            if display.scale_factor != max_scale:
                new_width = int(width * max_scale / display.scale_factor)
                new_height = int(height * max_scale / display.scale_factor)
                display_image = display_image.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS
                )

            # Paste onto canvas
            canvas.paste(display_image, (paste_x, paste_y))

        # Convert to bytes
        output = io.BytesIO()
        canvas.save(output, format='PNG')
        image_bytes = output.getvalue()

        return ScreenshotResult(
            image_bytes=image_bytes,
            width=canvas_width,
            height=canvas_height,
            format="PNG",
            combined_space=combined_space,
            display_info=displays,
            scale_factor=max_scale
        )

    def coordinate_to_display(self, x: float, y: float) -> Optional[Tuple[DisplayInfo, float, float]]:
        """
        Find which display contains the given global coordinates.

        Args:
            x: Global X coordinate
            y: Global Y coordinate

        Returns:
            Tuple of (DisplayInfo, local_x, local_y) if found, None otherwise.
        """
        displays = self.get_displays()

        for display in displays:
            if display.bounds.contains_point(x, y):
                local_x, local_y = display.bounds.to_local(x, y)
                return (display, local_x, local_y)

        return None

    def display_to_global(
        self,
        display_id: int,
        local_x: float,
        local_y: float
    ) -> Optional[Tuple[float, float]]:
        """
        Convert display-local coordinates to global screen coordinates.

        Args:
            display_id: The display ID
            local_x: X coordinate relative to the display's top-left
            local_y: Y coordinate relative to the display's top-left

        Returns:
            Tuple of (global_x, global_y) if display found, None otherwise.
        """
        displays = self.get_displays()

        for display in displays:
            if display.display_id == display_id:
                return display.bounds.to_global(local_x, local_y)

        return None

    def screenshot_coords_to_screen(
        self,
        screenshot_x: float,
        screenshot_y: float,
        screenshot_result: ScreenshotResult
    ) -> Tuple[float, float]:
        """
        Convert coordinates in a stitched screenshot to actual screen coordinates.

        Args:
            screenshot_x: X coordinate in the screenshot image
            screenshot_y: Y coordinate in the screenshot image
            screenshot_result: The ScreenshotResult from capture_all_displays()

        Returns:
            Tuple of (screen_x, screen_y) in global screen coordinates.
        """
        if screenshot_result.combined_space is None:
            raise ValueError("Screenshot result does not contain combined space info")

        # Convert from pixel coords to logical coords
        scale = screenshot_result.scale_factor
        logical_x = screenshot_x / scale
        logical_y = screenshot_y / scale

        # Convert from normalized to global
        return screenshot_result.combined_space.denormalize_coordinates(logical_x, logical_y)

    def _cgimage_to_bytes(self, image_ref: Any, width: int, height: int) -> bytes:
        """Convert a CGImage to PNG bytes."""
        # Get raw pixel data
        data_provider = CGImageGetDataProvider(image_ref)
        data = CGDataProviderCopyData(data_provider)

        # Create PIL Image from raw data
        # CGImage data is in BGRA format
        bytes_per_row = CGImageGetBytesPerRow(image_ref)

        # Convert to numpy array then PIL Image
        try:
            import numpy as np
            arr = np.frombuffer(data, dtype=np.uint8)
            arr = arr.reshape((height, bytes_per_row // 4, 4))
            # Take only the needed width (bytes_per_row may be padded)
            arr = arr[:, :width, :]
            # Convert BGRA to RGBA
            arr = arr[:, :, [2, 1, 0, 3]]
            image = Image.fromarray(arr, 'RGBA')
        except ImportError:
            # Fallback without numpy - less efficient
            pixels = []
            row_bytes = bytes_per_row
            for y in range(height):
                for x in range(width):
                    idx = y * row_bytes + x * 4
                    b, g, r, a = data[idx:idx+4]
                    pixels.append((r, g, b, a))
            image = Image.new('RGBA', (width, height))
            image.putdata(pixels)

        # Convert to PNG bytes
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()

    def clear_cache(self) -> None:
        """Clear the display cache to force re-enumeration on next call."""
        self._display_cache = None
        self._combined_space = None

    def get_windows(
        self,
        app_name: Optional[str] = None,
        on_screen_only: bool = True
    ) -> List[WindowInfo]:
        """
        Get information about visible windows.

        Args:
            app_name: Filter by application name (case-insensitive contains match).
                     If None, returns all windows.
            on_screen_only: If True, only return windows currently visible on screen.

        Returns:
            List of WindowInfo objects for matching windows.
        """
        # Get window list from Quartz
        options = kCGWindowListOptionOnScreenOnly if on_screen_only else 0
        options |= kCGWindowListExcludeDesktopElements

        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        if window_list is None:
            return []

        windows = []
        displays = self.get_displays()

        for window_dict in window_list:
            # Get window properties
            owner_name = window_dict.get('kCGWindowOwnerName', '')
            window_name = window_dict.get('kCGWindowName', '')
            window_id = window_dict.get('kCGWindowNumber', 0)
            layer = window_dict.get('kCGWindowLayer', 0)
            is_on_screen = window_dict.get('kCGWindowIsOnscreen', False)

            # Filter by app name if specified
            if app_name is not None:
                if app_name.lower() not in owner_name.lower():
                    continue

            # Skip windows without bounds
            bounds_dict = window_dict.get('kCGWindowBounds')
            if bounds_dict is None:
                continue

            # Parse bounds
            bounds = DisplayBounds(
                x=bounds_dict.get('X', 0),
                y=bounds_dict.get('Y', 0),
                width=bounds_dict.get('Width', 0),
                height=bounds_dict.get('Height', 0)
            )

            # Skip very small windows (likely menu items or hidden)
            if bounds.width < 10 or bounds.height < 10:
                continue

            # Find which display this window is on
            display_id = None
            center_x = bounds.x + bounds.width / 2
            center_y = bounds.y + bounds.height / 2
            for display in displays:
                if display.bounds.contains_point(center_x, center_y):
                    display_id = display.display_id
                    break

            window_info = WindowInfo(
                window_id=window_id,
                app_name=owner_name,
                window_title=window_name or '',
                bounds=bounds,
                display_id=display_id,
                is_on_screen=is_on_screen,
                layer=layer
            )
            windows.append(window_info)

        # Sort by layer (higher layers first - more visible)
        windows.sort(key=lambda w: -w.layer)

        return windows

    def capture_window(
        self,
        app_name: Optional[str] = None,
        window_id: Optional[int] = None,
        include_shadow: bool = False
    ) -> ScreenshotResult:
        """
        Capture screenshot of a specific application window.

        Args:
            app_name: Application name to capture (e.g., "Unity", "Safari").
                     If multiple windows match, captures the topmost one.
            window_id: Specific window ID to capture. Takes precedence over app_name.
            include_shadow: If True, include the window's shadow in the capture.

        Returns:
            ScreenshotResult containing the captured window image.

        Raises:
            ValueError: If no matching window is found.
            RuntimeError: If screenshot capture fails.
        """
        # Find the window to capture
        target_window: Optional[WindowInfo] = None

        if window_id is not None:
            # Find by specific window ID
            windows = self.get_windows(on_screen_only=True)
            for w in windows:
                if w.window_id == window_id:
                    target_window = w
                    break
            if target_window is None:
                raise ValueError(f"Window with ID {window_id} not found")
        elif app_name is not None:
            # Find by app name (get topmost window)
            windows = self.get_windows(app_name=app_name, on_screen_only=True)
            if not windows:
                raise ValueError(f"No windows found for application '{app_name}'")
            target_window = windows[0]  # Already sorted by layer
        else:
            raise ValueError("Either app_name or window_id must be provided")

        # Use screencapture CLI for window capture (more reliable than CGWindowListCreateImage)
        # The -l flag captures a specific window by ID
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Build screencapture command
            cmd = ['screencapture', '-l', str(target_window.window_id)]
            if not include_shadow:
                cmd.append('-o')  # No shadow
            cmd.append(tmp_path)

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"screencapture failed: {result.stderr}")

            # Read the captured image
            with open(tmp_path, 'rb') as f:
                image_bytes = f.read()

            # Get image dimensions using PIL
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size

            # Get scale factor from display
            scale_factor = 1.0
            if target_window.display_id is not None:
                displays = self.get_displays()
                for d in displays:
                    if d.display_id == target_window.display_id:
                        scale_factor = d.scale_factor
                        break

            return ScreenshotResult(
                image_bytes=image_bytes,
                width=width,
                height=height,
                format="PNG",
                scale_factor=scale_factor,
                window_info=target_window,
                timestamp=datetime.now()
            )

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_window_display(self, app_name: str) -> Optional[DisplayInfo]:
        """
        Find which display contains the specified application's main window.

        Args:
            app_name: Application name to find (case-insensitive contains match).

        Returns:
            DisplayInfo for the display containing the window, or None if not found.
        """
        windows = self.get_windows(app_name=app_name, on_screen_only=True)
        if not windows:
            return None

        # Get the topmost window
        target_window = windows[0]

        if target_window.display_id is None:
            return None

        # Find the matching display info
        displays = self.get_displays()
        for display in displays:
            if display.display_id == target_window.display_id:
                return display

        return None


# Convenience functions for simple usage

def capture_screenshot() -> bytes:
    """
    Capture a screenshot of all displays.

    Returns:
        PNG image bytes of the combined screenshot.
    """
    capture = MultiMonitorCapture()
    result = capture.capture_all_displays()
    return result.image_bytes


def get_display_info() -> List[DisplayInfo]:
    """
    Get information about all connected displays.

    Returns:
        List of DisplayInfo for each display.
    """
    capture = MultiMonitorCapture()
    return capture.get_displays()


def coordinate_to_display(x: float, y: float) -> Optional[Tuple[DisplayInfo, float, float]]:
    """
    Find which display contains the given coordinates.

    Args:
        x: Global X coordinate
        y: Global Y coordinate

    Returns:
        Tuple of (DisplayInfo, local_x, local_y) if found, None otherwise.
    """
    capture = MultiMonitorCapture()
    return capture.coordinate_to_display(x, y)


def display_to_global(display_id: int, local_x: float, local_y: float) -> Optional[Tuple[float, float]]:
    """
    Convert display-local coordinates to global coordinates.

    Args:
        display_id: The display ID
        local_x: X coordinate relative to display
        local_y: Y coordinate relative to display

    Returns:
        Tuple of (global_x, global_y) if display found, None otherwise.
    """
    capture = MultiMonitorCapture()
    return capture.display_to_global(display_id, local_x, local_y)


def get_windows(app_name: Optional[str] = None) -> List[WindowInfo]:
    """
    Get information about visible windows.

    Args:
        app_name: Filter by application name (optional).

    Returns:
        List of WindowInfo objects for matching windows.
    """
    capture = MultiMonitorCapture()
    return capture.get_windows(app_name=app_name)


def capture_window(app_name: str, include_shadow: bool = False) -> ScreenshotResult:
    """
    Capture screenshot of a specific application window.

    Args:
        app_name: Application name to capture (e.g., "Unity", "Safari").
        include_shadow: If True, include the window's shadow in the capture.

    Returns:
        ScreenshotResult containing the captured window image.
    """
    capture = MultiMonitorCapture()
    return capture.capture_window(app_name=app_name, include_shadow=include_shadow)


def get_window_display(app_name: str) -> Optional[DisplayInfo]:
    """
    Find which display contains the specified application's window.

    Args:
        app_name: Application name to find.

    Returns:
        DisplayInfo for the display containing the window, or None if not found.
    """
    capture = MultiMonitorCapture()
    return capture.get_window_display(app_name)


def save_screenshot_with_timestamp(
    directory: Optional[Union[str, Path]] = None,
    prefix: str = "screenshot"
) -> Tuple[Path, ScreenshotResult]:
    """
    Capture and save a screenshot with timestamp in filename.

    Args:
        directory: Directory to save to. Defaults to .claude-loop/screenshots/
        prefix: Filename prefix (default: "screenshot").

    Returns:
        Tuple of (saved_path, ScreenshotResult).
    """
    capture = MultiMonitorCapture()
    result = capture.capture_all_displays()
    result.timestamp = datetime.now()

    ts = result.timestamp.strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{ts}.png"

    saved_path = result.save(directory=directory, filename=filename, include_timestamp=False)

    return saved_path, result


def get_display_list() -> List[Dict[str, Any]]:
    """
    Get a list of connected displays with their properties.
    Alias for compatibility - returns display info as dictionaries.

    Returns:
        List of display information dictionaries with:
        - display_id: Display identifier
        - is_primary: Whether this is the main display
        - is_retina: Whether this is a Retina display
        - width, height: Logical dimensions in points
        - pixel_width, pixel_height: Native resolution
        - x, y: Position in global coordinate space
        - scale_factor: Retina scale factor (1.0 for non-Retina)
    """
    capture = MultiMonitorCapture()
    displays = capture.get_displays()

    return [
        {
            "display_id": d.display_id,
            "is_primary": d.is_primary,
            "is_retina": d.is_retina,
            "width": d.bounds.width,
            "height": d.bounds.height,
            "pixel_width": d.bounds.pixel_width,
            "pixel_height": d.bounds.pixel_height,
            "x": d.bounds.x,
            "y": d.bounds.y,
            "scale_factor": d.scale_factor,
            "arrangement": d.arrangement.value,
        }
        for d in displays
    ]
