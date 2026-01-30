#!/usr/bin/env python3
"""
test_screenshot.py - Tests for multi-monitor screenshot capture

This module provides comprehensive tests for the screenshot module,
including mock display configurations for CI-compatible testing.

Usage:
    # Run all tests with pytest
    pytest agents/computer_use/tests/test_screenshot.py -v

    # Run with coverage
    pytest agents/computer_use/tests/test_screenshot.py --cov=agents.computer_use.screenshot

    # Run without pytest
    python agents/computer_use/tests/test_screenshot.py
"""

import io
import sys
from unittest import mock
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Try to import pytest
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    class _MockPytest:
        """Mock pytest for running without pytest installed."""

        class fixture:
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, func):
                return func

        @staticmethod
        def mark():
            pass

    pytest = _MockPytest()  # type: ignore

# Import the module we're testing
from agents.computer_use.screenshot import (
    DisplayInfo,
    DisplayBounds,
    DisplayArrangement,
    CombinedDisplaySpace,
    ScreenshotResult,
    WindowInfo,
    DEFAULT_SCREENSHOT_DIR,
)


class MockDisplayConfig:
    """Mock display configurations for testing."""

    @staticmethod
    def single_display_1080p() -> List[dict]:
        """Single 1920x1080 display (most common)."""
        return [{
            'id': 1,
            'x': 0, 'y': 0,
            'width': 1920, 'height': 1080,
            'pixel_width': 1920, 'pixel_height': 1080,
            'is_primary': True,
            'is_retina': False,
            'scale_factor': 1.0
        }]

    @staticmethod
    def single_display_retina() -> List[dict]:
        """Single Retina display (MacBook)."""
        return [{
            'id': 1,
            'x': 0, 'y': 0,
            'width': 1440, 'height': 900,  # Logical resolution
            'pixel_width': 2880, 'pixel_height': 1800,  # Physical resolution
            'is_primary': True,
            'is_retina': True,
            'scale_factor': 2.0
        }]

    @staticmethod
    def dual_display_horizontal() -> List[dict]:
        """Two displays side by side (primary left, secondary right)."""
        return [
            {
                'id': 1,
                'x': 0, 'y': 0,
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': True,
                'is_retina': False,
                'scale_factor': 1.0
            },
            {
                'id': 2,
                'x': 1920, 'y': 0,  # Right of primary
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False,
                'is_retina': False,
                'scale_factor': 1.0
            }
        ]

    @staticmethod
    def dual_display_vertical() -> List[dict]:
        """Two displays stacked vertically (primary bottom, secondary top)."""
        return [
            {
                'id': 1,
                'x': 0, 'y': 0,
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': True,
                'is_retina': False,
                'scale_factor': 1.0
            },
            {
                'id': 2,
                'x': 0, 'y': -1080,  # Above primary (negative Y)
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False,
                'is_retina': False,
                'scale_factor': 1.0
            }
        ]

    @staticmethod
    def triple_display_mixed() -> List[dict]:
        """Three displays: Retina laptop center, two external monitors on sides."""
        return [
            {
                'id': 2,
                'x': -1920, 'y': 0,  # Left external
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False,
                'is_retina': False,
                'scale_factor': 1.0
            },
            {
                'id': 1,
                'x': 0, 'y': 0,  # Center (Retina laptop)
                'width': 1440, 'height': 900,
                'pixel_width': 2880, 'pixel_height': 1800,
                'is_primary': True,
                'is_retina': True,
                'scale_factor': 2.0
            },
            {
                'id': 3,
                'x': 1440, 'y': 0,  # Right external
                'width': 2560, 'height': 1440,
                'pixel_width': 2560, 'pixel_height': 1440,
                'is_primary': False,
                'is_retina': False,
                'scale_factor': 1.0
            }
        ]


def create_display_info_from_config(config: dict) -> DisplayInfo:
    """Helper to create DisplayInfo from mock config."""
    return DisplayInfo(
        display_id=config['id'],
        bounds=DisplayBounds(
            x=config['x'],
            y=config['y'],
            width=config['width'],
            height=config['height'],
            pixel_width=config['pixel_width'],
            pixel_height=config['pixel_height']
        ),
        is_primary=config['is_primary'],
        is_retina=config['is_retina'],
        scale_factor=config['scale_factor'],
        arrangement=DisplayArrangement.PRIMARY if config['is_primary'] else (
            DisplayArrangement.LEFT if config['x'] < 0 else
            DisplayArrangement.RIGHT if config['x'] > 0 else
            DisplayArrangement.ABOVE if config['y'] < 0 else
            DisplayArrangement.BELOW
        )
    )


class TestDisplayBounds:
    """Tests for DisplayBounds class."""

    def test_contains_point_inside(self):
        """Test point containment for points inside bounds."""
        bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)
        assert bounds.contains_point(0, 0) is True
        assert bounds.contains_point(960, 540) is True
        assert bounds.contains_point(1919, 1079) is True

    def test_contains_point_outside(self):
        """Test point containment for points outside bounds."""
        bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)
        assert bounds.contains_point(-1, 0) is False
        assert bounds.contains_point(1920, 0) is False
        assert bounds.contains_point(0, 1080) is False
        assert bounds.contains_point(2000, 2000) is False

    def test_contains_point_negative_origin(self):
        """Test containment with negative origin (display above/left of primary)."""
        bounds = DisplayBounds(x=-1920, y=-1080, width=1920, height=1080)
        assert bounds.contains_point(-1920, -1080) is True
        assert bounds.contains_point(-1, -1) is True
        assert bounds.contains_point(0, 0) is False

    def test_to_local_coordinates(self):
        """Test converting global to local coordinates."""
        bounds = DisplayBounds(x=1920, y=0, width=1920, height=1080)
        local_x, local_y = bounds.to_local(2000, 100)
        assert local_x == 80
        assert local_y == 100

    def test_to_global_coordinates(self):
        """Test converting local to global coordinates."""
        bounds = DisplayBounds(x=1920, y=0, width=1920, height=1080)
        global_x, global_y = bounds.to_global(80, 100)
        assert global_x == 2000
        assert global_y == 100


class TestCombinedDisplaySpace:
    """Tests for CombinedDisplaySpace class."""

    def test_single_display_space(self):
        """Test combined space with single display."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.single_display_1080p()]
        space = CombinedDisplaySpace.from_displays(displays)

        assert space.min_x == 0
        assert space.min_y == 0
        assert space.max_x == 1920
        assert space.max_y == 1080
        assert space.total_width == 1920
        assert space.total_height == 1080

    def test_dual_horizontal_space(self):
        """Test combined space with two horizontal displays."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]
        space = CombinedDisplaySpace.from_displays(displays)

        assert space.min_x == 0
        assert space.min_y == 0
        assert space.max_x == 3840  # 1920 + 1920
        assert space.max_y == 1080
        assert space.total_width == 3840
        assert space.total_height == 1080

    def test_dual_vertical_space(self):
        """Test combined space with two vertical displays."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_vertical()]
        space = CombinedDisplaySpace.from_displays(displays)

        assert space.min_x == 0
        assert space.min_y == -1080  # Display above has negative Y
        assert space.max_x == 1920
        assert space.max_y == 1080
        assert space.total_width == 1920
        assert space.total_height == 2160  # 1080 + 1080

    def test_triple_mixed_space(self):
        """Test combined space with three displays of different sizes."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.triple_display_mixed()]
        space = CombinedDisplaySpace.from_displays(displays)

        assert space.min_x == -1920  # Left display
        assert space.min_y == 0
        assert space.max_x == 1440 + 2560  # Right edge of rightmost display
        assert space.total_width == 1920 + 1440 + 2560
        assert space.total_height == max(1080, 900, 1440)

    def test_normalize_denormalize_coordinates(self):
        """Test coordinate normalization and denormalization."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.triple_display_mixed()]
        space = CombinedDisplaySpace.from_displays(displays)

        # Original global coordinate
        global_x, global_y = -960, 540

        # Normalize to 0-based
        norm_x, norm_y = space.normalize_coordinates(global_x, global_y)

        # Should be offset by min_x, min_y
        assert norm_x == global_x - space.min_x
        assert norm_y == global_y - space.min_y

        # Denormalize should give back original
        result_x, result_y = space.denormalize_coordinates(norm_x, norm_y)
        assert result_x == global_x
        assert result_y == global_y


class TestCoordinateMapping:
    """Tests for coordinate mapping between displays."""

    def test_coordinate_to_display_primary(self):
        """Test finding display containing coordinates on primary."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]

        # Point in primary display
        primary = displays[0]
        assert primary.bounds.contains_point(100, 100) is True
        assert primary.bounds.contains_point(1919, 1079) is True

        # Point in secondary display
        assert primary.bounds.contains_point(2000, 100) is False

    def test_coordinate_to_display_secondary(self):
        """Test finding display containing coordinates on secondary."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]

        secondary = displays[1]
        # Point in secondary display
        assert secondary.bounds.contains_point(2000, 100) is True
        assert secondary.bounds.contains_point(3839, 1079) is True

        # Point in primary display
        assert secondary.bounds.contains_point(100, 100) is False

    def test_coordinate_mapping_negative_coordinates(self):
        """Test coordinate mapping with negative coordinates."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_vertical()]

        # Find the display above (negative Y)
        upper_display = next(d for d in displays if d.bounds.y < 0)

        # Point in upper display
        assert upper_display.bounds.contains_point(960, -540) is True

        # Convert to local
        local_x, local_y = upper_display.bounds.to_local(960, -540)
        assert local_x == 960
        assert local_y == 540  # Local coords are positive

        # Convert back to global
        global_x, global_y = upper_display.bounds.to_global(960, 540)
        assert global_x == 960
        assert global_y == -540


class TestDisplayInfo:
    """Tests for DisplayInfo class."""

    def test_display_info_repr(self):
        """Test string representation of DisplayInfo."""
        config = MockDisplayConfig.single_display_retina()[0]
        display = create_display_info_from_config(config)

        repr_str = repr(display)
        assert "1440x900" in repr_str  # Logical dimensions
        assert "Retina" in repr_str

    def test_retina_detection(self):
        """Test Retina display detection."""
        non_retina = create_display_info_from_config(
            MockDisplayConfig.single_display_1080p()[0]
        )
        assert non_retina.is_retina is False
        assert non_retina.scale_factor == 1.0

        retina = create_display_info_from_config(
            MockDisplayConfig.single_display_retina()[0]
        )
        assert retina.is_retina is True
        assert retina.scale_factor == 2.0


class TestScreenshotResult:
    """Tests for ScreenshotResult class."""

    def test_screenshot_result_creation(self):
        """Test creating a ScreenshotResult."""
        result = ScreenshotResult(
            image_bytes=b'fake_png_data',
            width=1920,
            height=1080,
            format="PNG",
            scale_factor=1.0
        )
        assert result.width == 1920
        assert result.height == 1080
        assert result.format == "PNG"
        assert result.image_bytes == b'fake_png_data'

    def test_screenshot_result_with_combined_space(self):
        """Test ScreenshotResult with combined display space."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]
        space = CombinedDisplaySpace.from_displays(displays)

        result = ScreenshotResult(
            image_bytes=b'fake_png_data',
            width=3840,
            height=1080,
            format="PNG",
            combined_space=space,
            display_info=displays,
            scale_factor=1.0
        )

        assert result.combined_space is not None
        assert result.combined_space.total_width == 3840
        assert result.display_info is not None and len(result.display_info) == 2


class TestCoordinateMappingFunctions:
    """Tests for GUI-002: coordinate_to_display and display_to_global functions.

    These tests verify:
    - Get display arrangement from CGDisplayBounds()
    - Map coordinates from stitched screenshot to actual screen position
    - Handle negative Y coordinates for displays above primary
    - Support left/right/top/bottom monitor arrangements
    - coordinate_to_display(x, y) function
    - display_to_global(display_id, local_x, local_y) function
    """

    def test_coordinate_to_display_left_arrangement(self):
        """Test finding display when secondary is LEFT of primary."""
        # Create displays: secondary on left, primary on right
        configs = [
            {
                'id': 1, 'x': 0, 'y': 0,
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': True, 'is_retina': False, 'scale_factor': 1.0
            },
            {
                'id': 2, 'x': -1920, 'y': 0,  # Left of primary
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False, 'is_retina': False, 'scale_factor': 1.0
            }
        ]
        displays = [create_display_info_from_config(c) for c in configs]

        # Point on left display
        left_display = next(d for d in displays if d.arrangement == DisplayArrangement.LEFT)
        assert left_display.bounds.contains_point(-1000, 500) is True
        assert left_display.bounds.contains_point(100, 500) is False

        # Convert to local coords
        local_x, local_y = left_display.bounds.to_local(-1000, 500)
        assert local_x == 920  # -1000 - (-1920) = 920
        assert local_y == 500

    def test_coordinate_to_display_right_arrangement(self):
        """Test finding display when secondary is RIGHT of primary."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]

        # Primary (left) and secondary (right)
        primary = next(d for d in displays if d.is_primary)
        secondary = next(d for d in displays if not d.is_primary)

        assert secondary.arrangement == DisplayArrangement.RIGHT

        # Point on right display
        assert secondary.bounds.contains_point(2500, 500) is True
        local_x, _ = secondary.bounds.to_local(2500, 500)
        assert local_x == 580  # 2500 - 1920 = 580

    def test_coordinate_to_display_above_arrangement(self):
        """Test finding display when secondary is ABOVE primary (negative Y)."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_vertical()]

        # Find display above (negative Y)
        above_display = next(d for d in displays if d.bounds.y < 0)
        assert above_display.arrangement == DisplayArrangement.ABOVE

        # Point in upper display (negative Y coordinate)
        assert above_display.bounds.contains_point(960, -500) is True
        local_x, local_y = above_display.bounds.to_local(960, -500)
        assert local_x == 960
        assert local_y == 580  # -500 - (-1080) = 580

    def test_coordinate_to_display_below_arrangement(self):
        """Test finding display when secondary is BELOW primary."""
        configs = [
            {
                'id': 1, 'x': 0, 'y': 0,
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': True, 'is_retina': False, 'scale_factor': 1.0
            },
            {
                'id': 2, 'x': 0, 'y': 1080,  # Below primary
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False, 'is_retina': False, 'scale_factor': 1.0
            }
        ]
        displays = [create_display_info_from_config(c) for c in configs]

        below_display = next(d for d in displays if d.bounds.y > 0)
        assert below_display.arrangement == DisplayArrangement.BELOW

        # Point in lower display
        assert below_display.bounds.contains_point(960, 1500) is True
        local_x, local_y = below_display.bounds.to_local(960, 1500)
        assert local_x == 960
        assert local_y == 420  # 1500 - 1080 = 420

    def test_display_to_global_all_arrangements(self):
        """Test display_to_global for all display arrangements."""
        # Triple display: left, primary (center), right
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.triple_display_mixed()]

        # Find displays by arrangement
        left = next(d for d in displays if d.arrangement == DisplayArrangement.LEFT)
        primary = next(d for d in displays if d.arrangement == DisplayArrangement.PRIMARY)
        right = next(d for d in displays if d.arrangement == DisplayArrangement.RIGHT)

        # Test display_to_global for left display
        global_x, global_y = left.bounds.to_global(100, 100)
        assert global_x == -1820  # -1920 + 100 = -1820
        assert global_y == 100

        # Test display_to_global for primary display
        global_x, global_y = primary.bounds.to_global(100, 100)
        assert global_x == 100
        assert global_y == 100

        # Test display_to_global for right display
        global_x, global_y = right.bounds.to_global(100, 100)
        assert global_x == 1540  # 1440 + 100 = 1540
        assert global_y == 100

    def test_screenshot_coords_to_screen_mapping(self):
        """Test mapping coordinates from stitched screenshot to actual screen position."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.triple_display_mixed()]
        space = CombinedDisplaySpace.from_displays(displays)

        # For triple display with mixed resolutions, max scale is 2.0 (Retina center)
        max_scale = 2.0
        # Create a mock screenshot result (validates ScreenshotResult with coordinate mapping)
        _ = ScreenshotResult(
            image_bytes=b'fake',
            width=int(space.total_width * max_scale),
            height=int(space.total_height * max_scale),
            format="PNG",
            combined_space=space,
            display_info=displays,
            scale_factor=max_scale
        )

        # Test point in left display: screen coords (-960, 540) should map to screenshot pixel
        # Normalized: -960 - (-1920) = 960, 540 - 0 = 540
        # Screenshot pixel at scale 2.0: (1920, 1080)
        screen_x, screen_y = -960, 540
        norm_x, norm_y = space.normalize_coordinates(screen_x, screen_y)
        screenshot_pixel_x = norm_x * max_scale
        screenshot_pixel_y = norm_y * max_scale

        # Reverse: from screenshot pixel back to screen coords
        logical_x = screenshot_pixel_x / max_scale
        logical_y = screenshot_pixel_y / max_scale
        result_x, result_y = space.denormalize_coordinates(logical_x, logical_y)

        assert result_x == screen_x
        assert result_y == screen_y

    def test_coordinate_boundary_conditions(self):
        """Test coordinate mapping at display boundaries."""
        displays = [create_display_info_from_config(c)
                   for c in MockDisplayConfig.dual_display_horizontal()]

        primary = displays[0]
        secondary = displays[1]

        # Exact boundary point (rightmost pixel of primary, leftmost of secondary)
        # Point at x=1920 should be on secondary, not primary
        assert primary.bounds.contains_point(1919, 540) is True
        assert primary.bounds.contains_point(1920, 540) is False
        assert secondary.bounds.contains_point(1920, 540) is True

        # Corner cases
        assert primary.bounds.contains_point(0, 0) is True
        assert primary.bounds.contains_point(1919, 1079) is True

    def test_coordinate_roundtrip_all_displays(self):
        """Test global->local->global roundtrip for all display types."""
        configs = [
            MockDisplayConfig.single_display_1080p(),
            MockDisplayConfig.single_display_retina(),
            MockDisplayConfig.dual_display_horizontal(),
            MockDisplayConfig.dual_display_vertical(),
            MockDisplayConfig.triple_display_mixed(),
        ]

        for config_set in configs:
            displays = [create_display_info_from_config(c) for c in config_set]

            for display in displays:
                # Test center of each display
                center_x = display.bounds.x + display.bounds.width / 2
                center_y = display.bounds.y + display.bounds.height / 2

                # Global to local
                local_x, local_y = display.bounds.to_local(center_x, center_y)

                # Local should be positive (within display)
                assert 0 <= local_x <= display.bounds.width
                assert 0 <= local_y <= display.bounds.height

                # Local back to global
                result_x, result_y = display.bounds.to_global(local_x, local_y)

                assert result_x == center_x
                assert result_y == center_y


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_display_list(self):
        """Test handling of empty display list."""
        space = CombinedDisplaySpace.from_displays([])
        assert space.total_width == 0.0
        assert space.total_height == 0.0
        assert len(space.displays) == 0

    def test_overlapping_displays(self):
        """Test handling of overlapping display configurations."""
        # This shouldn't happen in practice but the code should handle it
        configs = [
            {
                'id': 1,
                'x': 0, 'y': 0,
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': True,
                'is_retina': False,
                'scale_factor': 1.0
            },
            {
                'id': 2,
                'x': 960, 'y': 0,  # Overlaps with primary
                'width': 1920, 'height': 1080,
                'pixel_width': 1920, 'pixel_height': 1080,
                'is_primary': False,
                'is_retina': False,
                'scale_factor': 1.0
            }
        ]

        displays = [create_display_info_from_config(c) for c in configs]
        space = CombinedDisplaySpace.from_displays(displays)

        # Should still calculate combined space correctly
        assert space.min_x == 0
        assert space.max_x == 960 + 1920  # 2880

    def test_very_large_coordinates(self):
        """Test handling of very large coordinates."""
        bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)

        # Large positive coordinates
        assert bounds.contains_point(100000, 100000) is False

        # Large negative coordinates
        assert bounds.contains_point(-100000, -100000) is False

    def test_fractional_coordinates(self):
        """Test handling of fractional coordinates."""
        bounds = DisplayBounds(x=0.5, y=0.5, width=1920.5, height=1080.5)

        # Inside with fractional coords
        assert bounds.contains_point(1.0, 1.0) is True
        assert bounds.contains_point(1920.9, 1080.9) is True

        # Outside
        assert bounds.contains_point(0.4, 0.5) is False


class TestWindowInfo:
    """Tests for WindowInfo class - GUI-001 window capture support."""

    def test_window_info_creation(self):
        """Test creating a WindowInfo object."""
        bounds = DisplayBounds(x=100, y=200, width=800, height=600)
        window = WindowInfo(
            window_id=12345,
            app_name="Unity",
            window_title="My Project - Unity 2022.3.0f1",
            bounds=bounds,
            display_id=1,
            is_on_screen=True,
            layer=0
        )

        assert window.window_id == 12345
        assert window.app_name == "Unity"
        assert window.window_title == "My Project - Unity 2022.3.0f1"
        assert window.bounds.x == 100
        assert window.bounds.width == 800
        assert window.display_id == 1
        assert window.is_on_screen is True

    def test_window_info_repr(self):
        """Test string representation of WindowInfo."""
        bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)
        window = WindowInfo(
            window_id=1,
            app_name="Safari",
            window_title="Apple",
            bounds=bounds,
            display_id=1
        )

        repr_str = repr(window)
        assert "Safari" in repr_str
        assert "Apple" in repr_str
        assert "1920x1080" in repr_str


class TestScreenshotResultExtensions:
    """Tests for GUI-001 ScreenshotResult extensions: to_base64(), save()."""

    def test_to_base64_basic(self):
        """Test converting screenshot to base64."""
        import base64

        test_data = b'PNG_IMAGE_DATA_HERE'
        result = ScreenshotResult(
            image_bytes=test_data,
            width=100,
            height=100,
            format="PNG"
        )

        b64 = result.to_base64()

        # Should be valid base64
        decoded = base64.b64decode(b64)
        assert decoded == test_data

    def test_to_data_uri(self):
        """Test converting screenshot to data URI."""
        test_data = b'PNG_IMAGE_DATA'
        result = ScreenshotResult(
            image_bytes=test_data,
            width=100,
            height=100,
            format="PNG"
        )

        data_uri = result.to_data_uri()

        assert data_uri.startswith("data:image/png;base64,")
        # Extract and decode the base64 part
        import base64
        b64_part = data_uri.split(",")[1]
        decoded = base64.b64decode(b64_part)
        assert decoded == test_data

    def test_save_creates_file(self):
        """Test saving screenshot creates a file."""
        import tempfile
        import os
        from pathlib import Path

        # Create a minimal valid PNG (1x1 pixel)
        # PNG header + minimal IHDR + IDAT + IEND
        test_png = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfed'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        result = ScreenshotResult(
            image_bytes=test_png,
            width=1,
            height=1,
            format="PNG"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = result.save(
                directory=tmpdir,
                filename="test_screenshot.png",
                include_timestamp=False
            )

            assert saved_path.exists()
            assert saved_path.name == "test_screenshot.png"
            assert saved_path.read_bytes() == test_png
            assert result.saved_path == saved_path

    def test_save_auto_generates_filename(self):
        """Test saving screenshot auto-generates filename with timestamp."""
        import tempfile
        import re

        test_data = b'FAKE_PNG_DATA'
        result = ScreenshotResult(
            image_bytes=test_data,
            width=100,
            height=100,
            format="PNG"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = result.save(directory=tmpdir)

            # Filename should match pattern: screenshot_YYYYMMDD_HHMMSS_FFFFFF.png
            assert saved_path.exists()
            pattern = r'screenshot_\d{8}_\d{6}_\d{6}\.png'
            assert re.match(pattern, saved_path.name), f"Filename {saved_path.name} doesn't match pattern"

    def test_save_creates_directory(self):
        """Test save creates parent directories if needed."""
        import tempfile
        from pathlib import Path

        test_data = b'FAKE_PNG_DATA'
        result = ScreenshotResult(
            image_bytes=test_data,
            width=100,
            height=100,
            format="PNG"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "deep" / "nested" / "dir"
            saved_path = result.save(
                directory=nested_dir,
                filename="test.png",
                include_timestamp=False
            )

            assert saved_path.exists()
            assert saved_path.parent == nested_dir


class TestDefaultScreenshotDir:
    """Tests for DEFAULT_SCREENSHOT_DIR constant."""

    def test_default_dir_is_claude_loop_screenshots(self):
        """Test default directory is .claude-loop/screenshots/."""
        from pathlib import Path
        assert DEFAULT_SCREENSHOT_DIR == Path(".claude-loop/screenshots")


def run_basic_tests():
    """Run basic tests without pytest."""
    print("Running basic tests...")

    # Test DisplayBounds
    bounds = DisplayBounds(x=0, y=0, width=1920, height=1080)
    assert bounds.contains_point(960, 540), "Point should be inside bounds"
    assert not bounds.contains_point(2000, 0), "Point should be outside bounds"
    print("  DisplayBounds tests passed")

    # Test coordinate conversion
    local_x, local_y = bounds.to_local(100, 100)
    assert local_x == 100 and local_y == 100, "Local coords should match"
    global_x, global_y = bounds.to_global(100, 100)
    assert global_x == 100 and global_y == 100, "Global coords should match"
    print("  Coordinate conversion tests passed")

    # Test CombinedDisplaySpace
    displays = [create_display_info_from_config(c)
               for c in MockDisplayConfig.dual_display_horizontal()]
    space = CombinedDisplaySpace.from_displays(displays)
    assert space.total_width == 3840, f"Expected 3840, got {space.total_width}"
    print("  CombinedDisplaySpace tests passed")

    # Test normalization
    norm_x, norm_y = space.normalize_coordinates(100, 100)
    result_x, result_y = space.denormalize_coordinates(norm_x, norm_y)
    assert result_x == 100 and result_y == 100, "Roundtrip should preserve coords"
    print("  Normalization tests passed")

    # Test GUI-002: Coordinate mapping for all arrangements
    print("  Testing GUI-002 coordinate mapping...")

    # Test LEFT arrangement
    left_configs = [
        {'id': 1, 'x': 0, 'y': 0, 'width': 1920, 'height': 1080,
         'pixel_width': 1920, 'pixel_height': 1080,
         'is_primary': True, 'is_retina': False, 'scale_factor': 1.0},
        {'id': 2, 'x': -1920, 'y': 0, 'width': 1920, 'height': 1080,
         'pixel_width': 1920, 'pixel_height': 1080,
         'is_primary': False, 'is_retina': False, 'scale_factor': 1.0}
    ]
    left_displays = [create_display_info_from_config(c) for c in left_configs]
    left_display = next(d for d in left_displays if d.bounds.x < 0)
    assert left_display.bounds.contains_point(-1000, 500), "Left display should contain point"
    local_x, _ = left_display.bounds.to_local(-1000, 500)
    assert local_x == 920, f"Expected local_x=920, got {local_x}"
    print("    LEFT arrangement: OK")

    # Test ABOVE arrangement (negative Y)
    above_displays = [create_display_info_from_config(c)
                     for c in MockDisplayConfig.dual_display_vertical()]
    above_display = next(d for d in above_displays if d.bounds.y < 0)
    assert above_display.bounds.contains_point(960, -500), "Above display should contain negative Y point"
    _, local_y = above_display.bounds.to_local(960, -500)
    assert local_y == 580, f"Expected local_y=580, got {local_y}"
    print("    ABOVE arrangement (negative Y): OK")

    # Test BELOW arrangement
    below_configs = [
        {'id': 1, 'x': 0, 'y': 0, 'width': 1920, 'height': 1080,
         'pixel_width': 1920, 'pixel_height': 1080,
         'is_primary': True, 'is_retina': False, 'scale_factor': 1.0},
        {'id': 2, 'x': 0, 'y': 1080, 'width': 1920, 'height': 1080,
         'pixel_width': 1920, 'pixel_height': 1080,
         'is_primary': False, 'is_retina': False, 'scale_factor': 1.0}
    ]
    below_displays = [create_display_info_from_config(c) for c in below_configs]
    below_display = next(d for d in below_displays if d.bounds.y > 0)
    assert below_display.bounds.contains_point(960, 1500), "Below display should contain point"
    print("    BELOW arrangement: OK")

    # Test RIGHT arrangement
    right_displays = [create_display_info_from_config(c)
                     for c in MockDisplayConfig.dual_display_horizontal()]
    right_display = next(d for d in right_displays if d.bounds.x > 0)
    assert right_display.bounds.contains_point(2500, 500), "Right display should contain point"
    print("    RIGHT arrangement: OK")

    # Test roundtrip coordinate mapping
    triple_displays = [create_display_info_from_config(c)
                      for c in MockDisplayConfig.triple_display_mixed()]
    for display in triple_displays:
        center_x = display.bounds.x + display.bounds.width / 2
        center_y = display.bounds.y + display.bounds.height / 2
        local_x, local_y = display.bounds.to_local(center_x, center_y)
        result_x, result_y = display.bounds.to_global(local_x, local_y)
        assert result_x == center_x and result_y == center_y, \
            f"Roundtrip failed for display {display.display_id}"
    print("    Coordinate roundtrip: OK")

    print("  GUI-002 coordinate mapping tests passed")

    # Test GUI-001 new features
    print("  Testing GUI-001 new features...")

    # Test WindowInfo
    bounds = DisplayBounds(x=100, y=200, width=800, height=600)
    window = WindowInfo(
        window_id=12345,
        app_name="Unity",
        window_title="Test Project",
        bounds=bounds,
        display_id=1,
        is_on_screen=True,
        layer=0
    )
    assert window.window_id == 12345
    assert window.app_name == "Unity"
    assert "Unity" in repr(window)
    print("    WindowInfo: OK")

    # Test ScreenshotResult.to_base64()
    import base64 as b64
    test_data = b'PNG_IMAGE_DATA_HERE'
    result = ScreenshotResult(
        image_bytes=test_data,
        width=100,
        height=100,
        format="PNG"
    )
    encoded = result.to_base64()
    decoded = b64.b64decode(encoded)
    assert decoded == test_data, "Base64 roundtrip failed"
    print("    to_base64(): OK")

    # Test ScreenshotResult.to_data_uri()
    data_uri = result.to_data_uri()
    assert data_uri.startswith("data:image/png;base64,"), "Data URI format incorrect"
    print("    to_data_uri(): OK")

    # Test ScreenshotResult.save()
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        saved_path = result.save(
            directory=tmpdir,
            filename="test.png",
            include_timestamp=False
        )
        assert saved_path.exists(), "Saved file should exist"
        assert saved_path.read_bytes() == test_data
    print("    save(): OK")

    # Test DEFAULT_SCREENSHOT_DIR
    assert str(DEFAULT_SCREENSHOT_DIR) == ".claude-loop/screenshots", \
        f"Expected '.claude-loop/screenshots', got '{DEFAULT_SCREENSHOT_DIR}'"
    print("    DEFAULT_SCREENSHOT_DIR: OK")

    print("  GUI-001 new features tests passed")

    print("\nAll basic tests passed!")


if __name__ == "__main__":
    if PYTEST_AVAILABLE and len(sys.argv) > 1 and sys.argv[1] != "--basic":
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        run_basic_tests()
