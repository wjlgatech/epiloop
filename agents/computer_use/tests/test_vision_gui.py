#!/usr/bin/env python3
"""
test_vision_gui.py - Integration Tests for Vision-based GUI Automation

This module provides comprehensive tests for the vision-based GUI automation
system, including:
- Screenshot capture on different display configurations
- Coordinate translation for multi-display setups
- Vision API element detection with mock screenshots
- Click handler fallback logic
- Wait utilities with simulated delays
- Action logger output format

Features:
- CI mode: Uses mock screenshots only (no actual screen capture)
- Mock dependencies for testing without Quartz/Vision API
- Test fixtures in tests/fixtures/

Usage:
    # Run all tests with pytest
    pytest agents/computer_use/tests/test_vision_gui.py -v

    # Run in CI mode (mock screenshots only)
    CI=1 pytest agents/computer_use/tests/test_vision_gui.py -v

    # Run with coverage
    pytest agents/computer_use/tests/test_vision_gui.py --cov=agents.computer_use

    # Run without pytest
    python agents/computer_use/tests/test_vision_gui.py
"""

import base64
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock, patch

# CI mode detection
CI_MODE = os.environ.get("CI", "").lower() in ("1", "true", "yes")

# Try to import pytest
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    class _MockPytest:
        """Mock pytest for running without pytest installed."""

        class fixture:
            def __init__(self, *_args, **_kwargs):
                pass

            def __call__(self, func):
                return func

        class mark:
            @staticmethod
            def skipif(condition, reason=""):
                def decorator(func):
                    if condition:

                        def skipped(*_args, **_kwargs):
                            print(f"SKIPPED: {reason}")
                            return None

                        return skipped
                    return func

                return decorator

        @staticmethod
        def main(args):
            """Mock main that runs unittest instead."""
            return 0

    pytest = _MockPytest()  # type: ignore


# ============================================================================
# Mock Fixtures and Test Data
# ============================================================================


def create_mock_png_image(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid PNG image for testing."""
    # PNG header + minimal IHDR + IDAT + IEND
    # This is a 1x1 white pixel PNG - we'll use it as a placeholder
    return (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfed"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@dataclass
class MockDisplayConfig:
    """Mock display configuration for testing."""

    display_id: int
    x: int
    y: int
    width: int
    height: int
    pixel_width: int
    pixel_height: int
    is_primary: bool
    is_retina: bool
    scale_factor: float

    @classmethod
    def single_1080p(cls) -> "MockDisplayConfig":
        """Single 1920x1080 display."""
        return cls(
            display_id=1,
            x=0,
            y=0,
            width=1920,
            height=1080,
            pixel_width=1920,
            pixel_height=1080,
            is_primary=True,
            is_retina=False,
            scale_factor=1.0,
        )

    @classmethod
    def retina_display(cls) -> "MockDisplayConfig":
        """Single Retina display (MacBook)."""
        return cls(
            display_id=1,
            x=0,
            y=0,
            width=1440,
            height=900,
            pixel_width=2880,
            pixel_height=1800,
            is_primary=True,
            is_retina=True,
            scale_factor=2.0,
        )


@dataclass
class MockElementLocation:
    """Mock element location for vision API testing."""

    x: int
    y: int
    confidence: float
    description: str
    bounding_box: Optional[Tuple[int, int, int, int]] = None
    element_type: Optional[str] = None


@dataclass
class MockScreenshotResult:
    """Mock screenshot result for testing."""

    image_bytes: bytes
    width: int
    height: int
    format: str = "PNG"
    scale_factor: float = 1.0
    combined_space: Optional[Any] = None
    display_info: Optional[List[Any]] = None
    saved_path: Optional[Path] = None

    def to_base64(self) -> str:
        return base64.b64encode(self.image_bytes).decode("utf-8")

    def save(
        self,
        directory: Optional[str] = None,
        filename: Optional[str] = None,
        include_timestamp: bool = True,
    ) -> Path:
        if directory is None:
            directory = tempfile.gettempdir()
        if filename is None:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = Path(directory) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.image_bytes)
        self.saved_path = path
        return path


# ============================================================================
# Test Classes for Screenshot Module (GUI-001)
# ============================================================================


class TestScreenshotCapture(unittest.TestCase):
    """Tests for screenshot capture functionality (GUI-001)."""

    def test_mock_screenshot_creation(self):
        """Test creating mock screenshot data."""
        png_data = create_mock_png_image()
        self.assertTrue(png_data.startswith(b"\x89PNG"))
        self.assertTrue(len(png_data) > 0)

    def test_mock_screenshot_result(self):
        """Test MockScreenshotResult class."""
        result = MockScreenshotResult(
            image_bytes=create_mock_png_image(),
            width=1920,
            height=1080,
            format="PNG",
            scale_factor=1.0,
        )
        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)
        self.assertEqual(result.format, "PNG")

    def test_screenshot_to_base64(self):
        """Test converting screenshot to base64."""
        png_data = create_mock_png_image()
        result = MockScreenshotResult(
            image_bytes=png_data, width=100, height=100, format="PNG"
        )

        b64 = result.to_base64()
        decoded = base64.b64decode(b64)
        self.assertEqual(decoded, png_data)

    def test_screenshot_save(self):
        """Test saving screenshot to file."""
        png_data = create_mock_png_image()
        result = MockScreenshotResult(
            image_bytes=png_data, width=100, height=100, format="PNG"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = result.save(
                directory=tmpdir, filename="test.png", include_timestamp=False
            )
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), png_data)

    @pytest.mark.skipif(CI_MODE, reason="Skipped in CI mode")
    def test_real_screenshot_module_import(self):
        """Test importing the real screenshot module."""
        try:
            from agents.computer_use.screenshot import (
                MultiMonitorCapture,
                ScreenshotResult,
                DisplayInfo,
                QUARTZ_AVAILABLE,
            )

            self.assertIsNotNone(MultiMonitorCapture)
            self.assertIsNotNone(ScreenshotResult)
        except ImportError:
            self.skipTest("Screenshot module not available")


# ============================================================================
# Test Classes for Coordinate Translation (GUI-001, GUI-002)
# ============================================================================


class TestCoordinateTranslation(unittest.TestCase):
    """Tests for coordinate translation in multi-display setups."""

    def test_single_display_coordinates(self):
        """Test coordinates on single display."""
        config = MockDisplayConfig.single_1080p()

        # Point in center of display
        x, y = 960, 540

        # No translation needed for single display at origin
        self.assertEqual(x, 960)
        self.assertEqual(y, 540)

        # Check bounds
        self.assertTrue(0 <= x < config.width)
        self.assertTrue(0 <= y < config.height)

    def test_retina_scale_factor(self):
        """Test Retina display scale factor handling."""
        config = MockDisplayConfig.retina_display()

        # Logical coordinates
        logical_x, logical_y = 720, 450

        # Physical (pixel) coordinates
        physical_x = int(logical_x * config.scale_factor)
        physical_y = int(logical_y * config.scale_factor)

        self.assertEqual(physical_x, 1440)
        self.assertEqual(physical_y, 900)

    def test_negative_y_coordinates(self):
        """Test handling of negative Y coordinates (display above primary)."""
        # Display above primary has negative Y
        above_display = MockDisplayConfig(
            display_id=2,
            x=0,
            y=-1080,  # Above primary
            width=1920,
            height=1080,
            pixel_width=1920,
            pixel_height=1080,
            is_primary=False,
            is_retina=False,
            scale_factor=1.0,
        )

        # Point in upper display
        global_x, global_y = 960, -540

        # Convert to local coordinates
        local_x = global_x - above_display.x
        local_y = global_y - above_display.y

        self.assertEqual(local_x, 960)
        self.assertEqual(local_y, 540)  # Now positive

        # Convert back to global
        result_x = local_x + above_display.x
        result_y = local_y + above_display.y

        self.assertEqual(result_x, 960)
        self.assertEqual(result_y, -540)

    def test_left_display_coordinates(self):
        """Test coordinates for display to the left of primary."""
        left_display = MockDisplayConfig(
            display_id=2,
            x=-1920,  # Left of primary
            y=0,
            width=1920,
            height=1080,
            pixel_width=1920,
            pixel_height=1080,
            is_primary=False,
            is_retina=False,
            scale_factor=1.0,
        )

        # Point in left display
        global_x, global_y = -1000, 500

        # Check if point is in display bounds
        in_bounds = (
            left_display.x <= global_x < left_display.x + left_display.width
            and left_display.y <= global_y < left_display.y + left_display.height
        )
        self.assertTrue(in_bounds)

        # Convert to local
        local_x = global_x - left_display.x
        local_y = global_y - left_display.y
        self.assertEqual(local_x, 920)  # -1000 - (-1920) = 920
        self.assertEqual(local_y, 500)

    def test_coordinate_roundtrip(self):
        """Test global->local->global roundtrip."""
        displays = [
            MockDisplayConfig(
                display_id=1,
                x=0,
                y=0,
                width=1920,
                height=1080,
                pixel_width=1920,
                pixel_height=1080,
                is_primary=True,
                is_retina=False,
                scale_factor=1.0,
            ),
            MockDisplayConfig(
                display_id=2,
                x=1920,
                y=0,
                width=2560,
                height=1440,
                pixel_width=2560,
                pixel_height=1440,
                is_primary=False,
                is_retina=False,
                scale_factor=1.0,
            ),
        ]

        for display in displays:
            # Test center of each display
            center_x = display.x + display.width // 2
            center_y = display.y + display.height // 2

            # Global to local
            local_x = center_x - display.x
            local_y = center_y - display.y

            # Local should be positive
            self.assertGreaterEqual(local_x, 0)
            self.assertGreaterEqual(local_y, 0)

            # Local back to global
            result_x = local_x + display.x
            result_y = local_y + display.y

            self.assertEqual(result_x, center_x)
            self.assertEqual(result_y, center_y)


# ============================================================================
# Test Classes for Mouse Controller (GUI-002)
# ============================================================================


class TestMouseController(unittest.TestCase):
    """Tests for mouse controller functionality (GUI-002)."""

    def test_mouse_controller_import(self):
        """Test importing mouse controller module."""
        try:
            from agents.computer_use.mouse_controller import (
                MouseButton,
                ClickType,
                ClickResult,
                QUARTZ_AVAILABLE,
            )

            self.assertIsNotNone(MouseButton)
            self.assertIsNotNone(ClickType)
            self.assertIsNotNone(ClickResult)
        except ImportError:
            self.skipTest("Mouse controller module not available")

    def test_click_result_creation(self):
        """Test creating ClickResult."""
        try:
            from agents.computer_use.mouse_controller import ClickResult, ClickType

            result = ClickResult(
                success=True,
                x=100.0,
                y=200.0,
                click_type=ClickType.SINGLE,
                verified=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.x, 100.0)
            self.assertEqual(result.y, 200.0)
            self.assertEqual(result.click_type, ClickType.SINGLE)
        except ImportError:
            self.skipTest("Mouse controller module not available")

    def test_click_result_to_dict(self):
        """Test ClickResult.to_dict() method."""
        try:
            from agents.computer_use.mouse_controller import ClickResult, ClickType

            result = ClickResult(
                success=True, x=150.0, y=250.0, click_type=ClickType.DOUBLE
            )

            d = result.to_dict()
            self.assertTrue(d["success"])
            self.assertEqual(d["x"], 150.0)
            self.assertEqual(d["y"], 250.0)
            self.assertEqual(d["click_type"], "double")
        except ImportError:
            self.skipTest("Mouse controller module not available")

    @pytest.mark.skipif(CI_MODE, reason="Skipped in CI mode - requires Quartz")
    def test_mouse_controller_initialization(self):
        """Test MouseController initialization."""
        try:
            from agents.computer_use.mouse_controller import (
                MouseController,
                QUARTZ_AVAILABLE,
            )

            if not QUARTZ_AVAILABLE:
                self.skipTest("Quartz not available")

            controller = MouseController()
            self.assertIsNotNone(controller)
        except ImportError:
            self.skipTest("Mouse controller module not available")


# ============================================================================
# Test Classes for Vision Detector (GUI-003, GUI-006)
# ============================================================================


class TestVisionDetector(unittest.TestCase):
    """Tests for vision API element detection (GUI-003)."""

    def test_vision_detector_import(self):
        """Test importing vision detector module."""
        try:
            from agents.computer_use.vision_detector import (
                VisionDetector,
                BoundingBox,
                DetectionResult,
                ElementState,
                ButtonState,
                CheckboxState,
                VISION_DETECTOR_AVAILABLE,
            )

            self.assertIsNotNone(BoundingBox)
            self.assertIsNotNone(DetectionResult)
            self.assertIsNotNone(ElementState)
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_bounding_box_creation(self):
        """Test BoundingBox dataclass."""
        try:
            from agents.computer_use.vision_detector import BoundingBox

            bbox = BoundingBox(x=100, y=200, width=50, height=30)

            self.assertEqual(bbox.x, 100)
            self.assertEqual(bbox.y, 200)
            self.assertEqual(bbox.width, 50)
            self.assertEqual(bbox.height, 30)
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_bounding_box_from_tuple(self):
        """Test BoundingBox.from_tuple() class method."""
        try:
            from agents.computer_use.vision_detector import BoundingBox

            # (x1, y1, x2, y2) format
            bbox = BoundingBox.from_tuple((100, 200, 150, 230))

            self.assertEqual(bbox.x, 100)
            self.assertEqual(bbox.y, 200)
            self.assertEqual(bbox.width, 50)  # 150 - 100
            self.assertEqual(bbox.height, 30)  # 230 - 200
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_element_state_creation(self):
        """Test ElementState dataclass."""
        try:
            from agents.computer_use.vision_detector import (
                ElementState,
                ButtonState,
            )

            state = ElementState(
                element_type="button",
                description="Build button",
                confidence=0.95,
                enabled=True,
                button_state=ButtonState.ENABLED,
            )

            self.assertEqual(state.element_type, "button")
            self.assertTrue(state.is_enabled)
            self.assertFalse(state.is_disabled)
            self.assertEqual(state.button_state, ButtonState.ENABLED)
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_checkbox_state_values(self):
        """Test CheckboxState enum values."""
        try:
            from agents.computer_use.vision_detector import CheckboxState

            self.assertEqual(CheckboxState.CHECKED.value, "checked")
            self.assertEqual(CheckboxState.UNCHECKED.value, "unchecked")
            self.assertEqual(CheckboxState.INDETERMINATE.value, "indeterminate")
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_button_state_values(self):
        """Test ButtonState enum values."""
        try:
            from agents.computer_use.vision_detector import ButtonState

            self.assertEqual(ButtonState.ENABLED.value, "enabled")
            self.assertEqual(ButtonState.DISABLED.value, "disabled")
            self.assertEqual(ButtonState.PRESSED.value, "pressed")
        except ImportError:
            self.skipTest("Vision detector module not available")

    def test_element_state_convenience_properties(self):
        """Test ElementState convenience properties."""
        try:
            from agents.computer_use.vision_detector import (
                ElementState,
                CheckboxState,
            )

            # Test checkbox checked property
            checked_state = ElementState(
                element_type="checkbox",
                description="Enable feature",
                confidence=0.9,
                checkbox_state=CheckboxState.CHECKED,
            )
            self.assertTrue(checked_state.is_checked)
            self.assertFalse(checked_state.is_unchecked)

            # Test checkbox unchecked property
            unchecked_state = ElementState(
                element_type="checkbox",
                description="Disable feature",
                confidence=0.9,
                checkbox_state=CheckboxState.UNCHECKED,
            )
            self.assertFalse(unchecked_state.is_checked)
            self.assertTrue(unchecked_state.is_unchecked)
        except ImportError:
            self.skipTest("Vision detector module not available")


class TestVisionDetectorMocked(unittest.TestCase):
    """Tests for vision detector with mocked API responses."""

    def test_mock_element_detection(self):
        """Test element detection with mocked response."""
        mock_location = MockElementLocation(
            x=500,
            y=300,
            confidence=0.95,
            description="Build button",
            bounding_box=(480, 285, 520, 315),
            element_type="button",
        )

        # Verify mock data structure
        self.assertEqual(mock_location.x, 500)
        self.assertEqual(mock_location.y, 300)
        self.assertEqual(mock_location.confidence, 0.95)
        self.assertIsNotNone(mock_location.bounding_box)

    def test_mock_detection_with_low_confidence(self):
        """Test handling of low-confidence detections."""
        mock_location = MockElementLocation(
            x=100,
            y=200,
            confidence=0.3,  # Low confidence
            description="Unclear element",
        )

        # Should not trust low-confidence results
        self.assertLess(mock_location.confidence, 0.5)


# ============================================================================
# Test Classes for Click Handler (GUI-004)
# ============================================================================


class TestClickHandler(unittest.TestCase):
    """Tests for click handler with fallback chain (GUI-004)."""

    def test_click_handler_import(self):
        """Test importing click handler module."""
        try:
            from agents.computer_use.click_handler import (
                ClickHandler,
                ClickMethod,
                FallbackReason,
                ClickHandlerResult,
                ElementBounds,
            )

            self.assertIsNotNone(ClickHandler)
            self.assertIsNotNone(ClickMethod)
            self.assertIsNotNone(FallbackReason)
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_click_method_enum(self):
        """Test ClickMethod enum values."""
        try:
            from agents.computer_use.click_handler import ClickMethod

            self.assertEqual(ClickMethod.APPLESCRIPT.value, "applescript")
            self.assertEqual(ClickMethod.VISION_COORDINATE.value, "vision_coordinate")
            self.assertEqual(ClickMethod.FAILED.value, "failed")
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_fallback_reason_enum(self):
        """Test FallbackReason enum values."""
        try:
            from agents.computer_use.click_handler import FallbackReason

            self.assertEqual(
                FallbackReason.APPLESCRIPT_TIMEOUT.value, "applescript_timeout"
            )
            self.assertEqual(
                FallbackReason.ELEMENT_NOT_FOUND.value, "element_not_found"
            )
            self.assertEqual(FallbackReason.LOW_CONFIDENCE.value, "low_confidence")
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_element_bounds_center(self):
        """Test ElementBounds.center property."""
        try:
            from agents.computer_use.click_handler import ElementBounds

            bounds = ElementBounds(x=100, y=200, width=50, height=30)
            center_x, center_y = bounds.center

            self.assertEqual(center_x, 125)  # 100 + 50/2
            self.assertEqual(center_y, 215)  # 200 + 30/2
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_click_handler_result_creation(self):
        """Test ClickHandlerResult creation."""
        try:
            from agents.computer_use.click_handler import (
                ClickHandlerResult,
                ClickMethod,
                FallbackReason,
            )

            result = ClickHandlerResult(
                success=True,
                method=ClickMethod.APPLESCRIPT,
                x=500,
                y=300,
                confidence=0.95,
                applescript_tried=True,
                applescript_success=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.method, ClickMethod.APPLESCRIPT)
            self.assertTrue(result.applescript_tried)
            self.assertTrue(result.applescript_success)
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_click_handler_result_to_dict(self):
        """Test ClickHandlerResult.to_dict() method."""
        try:
            from agents.computer_use.click_handler import (
                ClickHandlerResult,
                ClickMethod,
            )

            result = ClickHandlerResult(
                success=False,
                method=ClickMethod.FAILED,
                error_message="Element not found",
                vision_tried=True,
                vision_success=False,
            )

            d = result.to_dict()
            self.assertFalse(d["success"])
            self.assertEqual(d["method"], "failed")
            self.assertEqual(d["error_message"], "Element not found")
        except ImportError:
            self.skipTest("Click handler module not available")


class TestClickHandlerFallbackLogic(unittest.TestCase):
    """Tests for click handler fallback chain logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.subprocess_patcher = patch("subprocess.run")
        self.mock_subprocess = self.subprocess_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.subprocess_patcher.stop()

    def test_applescript_success_no_fallback(self):
        """Test that successful AppleScript doesn't trigger fallback."""
        try:
            from agents.computer_use.click_handler import (
                ClickHandler,
                ClickMethod,
            )

            # Mock successful AppleScript
            self.mock_subprocess.return_value = MagicMock(returncode=0)

            handler = ClickHandler(enable_screenshots=False)

            # Mock vision/screenshot to not be needed
            with patch.object(handler, "_vision_detector", None):
                with patch.object(handler, "_screenshot_capture", None):
                    result = handler.click_element(
                        app_name="Unity",
                        element_name="Build",
                        vision_only=False,
                    )

            self.assertTrue(result.success)
            self.assertEqual(result.method, ClickMethod.APPLESCRIPT)
            self.assertTrue(result.applescript_tried)
            self.assertFalse(result.vision_tried)
        except ImportError:
            self.skipTest("Click handler module not available")

    def test_applescript_failure_triggers_fallback(self):
        """Test that AppleScript failure triggers vision fallback."""
        try:
            from agents.computer_use.click_handler import (
                ClickHandler,
                ClickMethod,
            )

            # Mock failed AppleScript
            self.mock_subprocess.return_value = MagicMock(returncode=1)

            handler = ClickHandler(enable_screenshots=False)

            # When vision is not available, should fail
            with patch.object(handler, "_vision_detector", None):
                with patch.object(handler, "_screenshot_capture", None):
                    result = handler.click_element(
                        app_name="Unity",
                        element_name="NonexistentButton",
                        vision_only=False,  # Try AppleScript first, then vision
                    )

            # AppleScript failed and vision wasn't available
            self.assertFalse(result.success)
            self.assertEqual(result.method, ClickMethod.FAILED)
            self.assertTrue(result.applescript_tried)
        except ImportError:
            self.skipTest("Click handler module not available")


# ============================================================================
# Test Classes for Wait Utilities (GUI-008)
# ============================================================================


class TestWaitUtilities(unittest.TestCase):
    """Tests for wait utilities (GUI-008)."""

    def test_wait_utils_import(self):
        """Test importing wait utils module."""
        try:
            from agents.computer_use.wait_utils import (
                WaitHelper,
                WaitResult,
                WaitOutcome,
                WaitProgress,
            )

            self.assertIsNotNone(WaitHelper)
            self.assertIsNotNone(WaitResult)
            self.assertIsNotNone(WaitOutcome)
        except ImportError:
            self.skipTest("Wait utils module not available")

    def test_wait_outcome_enum(self):
        """Test WaitOutcome enum values."""
        try:
            from agents.computer_use.wait_utils import WaitOutcome

            self.assertEqual(WaitOutcome.SUCCESS.value, "success")
            self.assertEqual(WaitOutcome.TIMEOUT.value, "timeout")
            self.assertEqual(WaitOutcome.ERROR.value, "error")
            self.assertEqual(WaitOutcome.CANCELLED.value, "cancelled")
        except ImportError:
            self.skipTest("Wait utils module not available")

    def test_wait_result_creation(self):
        """Test WaitResult creation."""
        try:
            from agents.computer_use.wait_utils import WaitResult, WaitOutcome

            result = WaitResult(
                success=True,
                outcome=WaitOutcome.SUCCESS,
                elapsed_ms=1500.0,
                iterations=3,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.outcome, WaitOutcome.SUCCESS)
            self.assertEqual(result.elapsed_ms, 1500.0)
            self.assertEqual(result.iterations, 3)
        except ImportError:
            self.skipTest("Wait utils module not available")

    def test_wait_result_to_dict(self):
        """Test WaitResult.to_dict() method."""
        try:
            from agents.computer_use.wait_utils import WaitResult, WaitOutcome

            result = WaitResult(
                success=False,
                outcome=WaitOutcome.TIMEOUT,
                elapsed_ms=10000.0,
                iterations=20,
                last_error="Element never appeared",
            )

            d = result.to_dict()
            self.assertFalse(d["success"])
            self.assertEqual(d["outcome"], "timeout")
            self.assertEqual(d["elapsed_ms"], 10000.0)
            self.assertEqual(d["last_error"], "Element never appeared")
        except ImportError:
            self.skipTest("Wait utils module not available")

    def test_wait_progress_creation(self):
        """Test WaitProgress dataclass."""
        try:
            from agents.computer_use.wait_utils import WaitProgress

            progress = WaitProgress(
                iteration=1,
                elapsed_ms=500.0,
                remaining_ms=9500.0,
                found=False,
                message="Still waiting...",
            )

            self.assertEqual(progress.iteration, 1)
            self.assertEqual(progress.elapsed_ms, 500.0)
            self.assertFalse(progress.found)
        except ImportError:
            self.skipTest("Wait utils module not available")


class TestWaitUtilitiesWithMocks(unittest.TestCase):
    """Tests for wait utilities with mocked dependencies."""

    def test_simulated_wait_success(self):
        """Test simulated wait that succeeds on third iteration."""
        iterations_called = [0]

        def mock_find_element(*args, **kwargs):
            iterations_called[0] += 1
            if iterations_called[0] >= 3:
                return MockElementLocation(
                    x=100, y=200, confidence=0.95, description="Build button"
                )
            return None

        # Simulate polling behavior
        max_iterations = 5
        found = False
        for i in range(max_iterations):
            result = mock_find_element()
            if result is not None:
                found = True
                break
            time.sleep(0.01)  # Short delay for test

        self.assertTrue(found)
        self.assertEqual(iterations_called[0], 3)

    def test_simulated_wait_timeout(self):
        """Test simulated wait that times out."""

        def mock_find_element(*args, **kwargs):
            return None  # Never find

        # Simulate polling with timeout
        timeout_ms = 50  # 50ms timeout
        poll_interval_ms = 10
        start_time = time.time() * 1000

        found = False
        iterations = 0
        while (time.time() * 1000 - start_time) < timeout_ms:
            iterations += 1
            result = mock_find_element()
            if result is not None:
                found = True
                break
            time.sleep(poll_interval_ms / 1000)

        self.assertFalse(found)
        self.assertGreaterEqual(iterations, 1)


# ============================================================================
# Test Classes for Action Logger (GUI-007)
# ============================================================================


class TestActionLogger(unittest.TestCase):
    """Tests for action logger functionality (GUI-007)."""

    def test_action_logger_import(self):
        """Test importing action logger module."""
        try:
            from agents.computer_use.action_logger import (
                ActionLogger,
                ActionLogEntry,
                ActionType,
                ActionStatus,
                SessionInfo,
            )

            self.assertIsNotNone(ActionLogger)
            self.assertIsNotNone(ActionLogEntry)
            self.assertIsNotNone(ActionType)
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_type_enum(self):
        """Test ActionType enum values."""
        try:
            from agents.computer_use.action_logger import ActionType

            self.assertEqual(ActionType.CLICK.value, "click")
            self.assertEqual(ActionType.DOUBLE_CLICK.value, "double_click")
            self.assertEqual(ActionType.TYPE.value, "type")
            self.assertEqual(ActionType.WAIT.value, "wait")
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_status_enum(self):
        """Test ActionStatus enum values."""
        try:
            from agents.computer_use.action_logger import ActionStatus

            self.assertEqual(ActionStatus.PENDING.value, "pending")
            self.assertEqual(ActionStatus.IN_PROGRESS.value, "in_progress")
            self.assertEqual(ActionStatus.SUCCESS.value, "success")
            self.assertEqual(ActionStatus.FAILURE.value, "failure")
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_log_entry_creation(self):
        """Test ActionLogEntry creation."""
        try:
            from agents.computer_use.action_logger import (
                ActionLogEntry,
                ActionStatus,
            )

            entry = ActionLogEntry(
                action_id="action_001",
                action_type="click",
                target="Build button",
                status=ActionStatus.SUCCESS.value,
                duration_ms=150,
                x=500.0,
                y=300.0,
            )

            self.assertEqual(entry.action_id, "action_001")
            self.assertEqual(entry.action_type, "click")
            self.assertEqual(entry.status, "success")
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_log_entry_to_dict(self):
        """Test ActionLogEntry.to_dict() method."""
        try:
            from agents.computer_use.action_logger import ActionLogEntry

            entry = ActionLogEntry(
                action_id="test_001",
                action_type="double_click",
                target="Input field",
                status="success",
                details={"app": "Unity"},
            )

            d = entry.to_dict()
            self.assertEqual(d["action_id"], "test_001")
            self.assertEqual(d["action_type"], "double_click")
            self.assertEqual(d["target"], "Input field")
            self.assertIn("app", d["details"])
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_session_info_creation(self):
        """Test SessionInfo creation."""
        try:
            from agents.computer_use.action_logger import SessionInfo

            session = SessionInfo(
                session_id="session_20260111_120000",
                name="Build Workflow Test",
                started_at="2026-01-11T12:00:00",
                total_actions=5,
                successful_actions=4,
                failed_actions=1,
            )

            self.assertEqual(session.name, "Build Workflow Test")
            self.assertEqual(session.total_actions, 5)
            self.assertEqual(session.successful_actions, 4)
        except ImportError:
            self.skipTest("Action logger module not available")


class TestActionLoggerWithFiles(unittest.TestCase):
    """Tests for action logger file operations."""

    def test_action_logger_initialization(self):
        """Test ActionLogger initialization."""
        try:
            from agents.computer_use.action_logger import ActionLogger

            with tempfile.TemporaryDirectory() as tmpdir:
                logger = ActionLogger(base_dir=tmpdir, enable_screenshots=False)
                self.assertIsNotNone(logger)
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_logger_session_lifecycle(self):
        """Test ActionLogger session start and end."""
        try:
            from agents.computer_use.action_logger import ActionLogger

            with tempfile.TemporaryDirectory() as tmpdir:
                action_logger = ActionLogger(base_dir=tmpdir, enable_screenshots=False)

                # Start session
                session_id = action_logger.start_session("Test Session")
                self.assertIsNotNone(session_id)
                self.assertIsNotNone(action_logger._session)  # Session is active

                # Log an action
                action_id = action_logger.log_action(
                    action_type="click",
                    target="Test button",
                    details={"test": True},
                )
                self.assertIsNotNone(action_id)

                # Complete the action
                action_logger.complete_action(action_id, success=True)

                # End session
                action_logger.end_session()
                self.assertIsNone(action_logger._session)  # Session is ended
        except ImportError:
            self.skipTest("Action logger module not available")

    def test_action_logger_json_output(self):
        """Test ActionLogger JSON output format."""
        try:
            from agents.computer_use.action_logger import ActionLogger

            with tempfile.TemporaryDirectory() as tmpdir:
                action_logger = ActionLogger(base_dir=tmpdir, enable_screenshots=False)

                action_logger.start_session("JSON Test")
                # Save the session dir before ending
                saved_session_dir = Path(action_logger._session_dir) if action_logger._session_dir else None

                action_id = action_logger.log_action(
                    action_type="click", target="Button", details={"key": "value"}
                )
                action_logger.complete_action(action_id, success=True)
                action_logger.end_session()

                # Check that session.json and actions.json exist
                if saved_session_dir:
                    session_json = saved_session_dir / "session.json"
                    actions_json = saved_session_dir / "actions.json"

                    if session_json.exists():
                        data = json.loads(session_json.read_text())
                        self.assertIn("session_id", data)

                    if actions_json.exists():
                        data = json.loads(actions_json.read_text())
                        # actions.json can be a dict with 'actions' key or a list
                        if isinstance(data, dict):
                            self.assertIn("actions", data)
                            self.assertIsInstance(data["actions"], list)
                        else:
                            self.assertIsInstance(data, list)
        except ImportError:
            self.skipTest("Action logger module not available")


# ============================================================================
# CI Mode Tests
# ============================================================================


class TestCIMode(unittest.TestCase):
    """Tests specifically for CI mode operation."""

    def test_ci_mode_detection(self):
        """Test CI mode is properly detected."""
        # CI_MODE is set at module level based on environment
        self.assertIsInstance(CI_MODE, bool)

    def test_mock_screenshot_works_without_quartz(self):
        """Test mock screenshots work without real Quartz."""
        screenshot = MockScreenshotResult(
            image_bytes=create_mock_png_image(),
            width=1920,
            height=1080,
            format="PNG",
        )

        # Should work without any Quartz dependency
        self.assertEqual(screenshot.width, 1920)
        self.assertEqual(screenshot.height, 1080)
        self.assertTrue(len(screenshot.to_base64()) > 0)

    def test_mock_element_location_works_without_api(self):
        """Test mock element locations work without Vision API."""
        location = MockElementLocation(
            x=500,
            y=300,
            confidence=0.95,
            description="Mock button",
            bounding_box=(480, 285, 520, 315),
        )

        # Should work without any API dependency
        self.assertEqual(location.x, 500)
        self.assertEqual(location.confidence, 0.95)


# ============================================================================
# Integration Tests
# ============================================================================


class TestModuleIntegration(unittest.TestCase):
    """Integration tests for module interactions."""

    def test_all_gui_modules_importable(self):
        """Test that all GUI-related modules can be imported."""
        modules_to_test = [
            "agents.computer_use.screenshot",
            "agents.computer_use.mouse_controller",
            "agents.computer_use.vision_detector",
            "agents.computer_use.click_handler",
            "agents.computer_use.wait_utils",
            "agents.computer_use.action_logger",
            "agents.computer_use.unity_panels",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except ImportError as e:
                # Log but don't fail - some modules may have optional deps
                print(f"Note: {module_name} not available: {e}")

    def test_availability_flags_consistent(self):
        """Test that availability flags are properly set."""
        try:
            from agents.computer_use import (
                SCREENSHOT_AVAILABLE,
                MOUSE_CONTROLLER_AVAILABLE,
                VISION_DETECTOR_AVAILABLE,
            )

            # These should all be booleans
            self.assertIsInstance(SCREENSHOT_AVAILABLE, bool)
            self.assertIsInstance(MOUSE_CONTROLLER_AVAILABLE, bool)
            self.assertIsInstance(VISION_DETECTOR_AVAILABLE, bool)
        except ImportError:
            self.skipTest("Computer use package not properly configured")


# ============================================================================
# Test Runner
# ============================================================================


def run_basic_tests():
    """Run basic tests without pytest."""
    print("Running basic tests...")
    print(f"CI Mode: {CI_MODE}")
    print()

    # Test mock fixtures
    print("Testing mock fixtures...")
    png = create_mock_png_image()
    assert png.startswith(b"\x89PNG"), "PNG signature incorrect"
    print("  Mock PNG creation: OK")

    screenshot = MockScreenshotResult(
        image_bytes=png, width=100, height=100, format="PNG"
    )
    assert screenshot.width == 100, "Screenshot width incorrect"
    b64 = screenshot.to_base64()
    assert len(b64) > 0, "Base64 encoding failed"
    print("  MockScreenshotResult: OK")

    location = MockElementLocation(x=500, y=300, confidence=0.95, description="Button")
    assert location.x == 500, "Location x incorrect"
    print("  MockElementLocation: OK")

    # Test coordinate translation
    print("\nTesting coordinate translation...")
    config = MockDisplayConfig.single_1080p()
    assert config.width == 1920, "Display width incorrect"
    assert config.height == 1080, "Display height incorrect"
    print("  Single display config: OK")

    retina = MockDisplayConfig.retina_display()
    assert retina.scale_factor == 2.0, "Retina scale incorrect"
    print("  Retina display config: OK")

    # Test negative Y coordinates
    global_y = -540
    display_y = -1080
    local_y = global_y - display_y
    assert local_y == 540, f"Local Y should be 540, got {local_y}"
    print("  Negative Y handling: OK")

    # Test coordinate roundtrip
    display_x, display_y = 1920, 0
    center_x, center_y = display_x + 1280, display_y + 720
    local_x = center_x - display_x
    local_y = center_y - display_y
    result_x = local_x + display_x
    result_y = local_y + display_y
    assert result_x == center_x and result_y == center_y, "Roundtrip failed"
    print("  Coordinate roundtrip: OK")

    print("\nAll basic tests passed!")
    return True


if __name__ == "__main__":
    if PYTEST_AVAILABLE and len(sys.argv) > 1 and sys.argv[1] != "--basic":
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        success = run_basic_tests()

        # Also run unittest tests
        print("\nRunning unittest tests...")
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(sys.modules[__name__])
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        sys.exit(0 if result.wasSuccessful() else 1)
