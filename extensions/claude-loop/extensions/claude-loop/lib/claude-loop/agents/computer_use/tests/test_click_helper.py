#!/usr/bin/env python3
"""
Tests for click_helper.py - Click operations with vision-based fallback.

These tests verify:
- ClickHelper initialization and lazy loading
- AppleScript click path (mocked)
- Vision-based fallback (mocked)
- Quartz mouse events (mocked)
- Coordinate conversion from vision to screen
- Before/after screenshot verification
"""

import unittest
from dataclasses import dataclass
from typing import Optional, Tuple, List
from unittest.mock import MagicMock, patch


# Create mock modules for dependencies that may not be available
class MockQuartz:
    """Mock Quartz module for testing."""
    CGEventCreateMouseEvent = MagicMock(return_value=MagicMock())
    CGEventPost = MagicMock()
    CGEventSetIntegerValueField = MagicMock()
    kCGHIDEventTap = 0
    kCGMouseButtonLeft = 0
    kCGEventMouseMoved = 5
    kCGEventLeftMouseDown = 1
    kCGEventLeftMouseUp = 2
    kCGEventLeftMouseDragged = 6


class MockCoreGraphics:
    """Mock CoreGraphics for testing."""
    kCGMouseEventClickState = 1


# Mock ElementLocation for testing
@dataclass
class MockElementLocation:
    """Mock ElementLocation for testing."""
    x: int
    y: int
    confidence: float
    description: str
    bounding_box: Optional[Tuple[int, int, int, int]] = None
    element_type: Optional[str] = None


# Mock ScreenshotResult for testing
@dataclass
class MockScreenshotResult:
    """Mock ScreenshotResult for testing."""
    image_bytes: bytes
    width: int
    height: int
    format: str = "PNG"
    combined_space: Optional[MagicMock] = None
    display_info: Optional[List] = None
    scale_factor: float = 1.0


class TestClickHelperModule(unittest.TestCase):
    """Test the click_helper module structure."""

    def test_module_imports(self):
        """Test that click_helper module can be imported."""
        try:
            from agents.computer_use.click_helper import (
                ClickMethod,
                ClickResult,
                ClickHelper,
                click_with_vision_fallback,
            )
            # Module imports successfully
            self.assertTrue(True)
        except ImportError as e:
            # Expected if Quartz is not available
            self.assertIn("Quartz", str(e))

    def test_click_method_enum(self):
        """Test ClickMethod enum values."""
        from agents.computer_use.click_helper import ClickMethod

        self.assertEqual(ClickMethod.APPLESCRIPT.value, "applescript")
        self.assertEqual(ClickMethod.VISION_QUARTZ.value, "vision_quartz")
        self.assertEqual(ClickMethod.COORDINATES.value, "coordinates")
        self.assertEqual(ClickMethod.FAILED.value, "failed")

    def test_click_result_dataclass(self):
        """Test ClickResult dataclass."""
        from agents.computer_use.click_helper import ClickResult, ClickMethod

        result = ClickResult(
            success=True,
            method=ClickMethod.APPLESCRIPT,
            x=100,
            y=200,
            confidence=0.95
        )

        self.assertTrue(result.success)
        self.assertEqual(result.method, ClickMethod.APPLESCRIPT)
        self.assertEqual(result.x, 100)
        self.assertEqual(result.y, 200)
        self.assertEqual(result.confidence, 0.95)

    def test_click_result_repr(self):
        """Test ClickResult string representation."""
        from agents.computer_use.click_helper import ClickResult, ClickMethod

        success_result = ClickResult(
            success=True,
            method=ClickMethod.VISION_QUARTZ,
            x=150,
            y=250
        )
        self.assertIn("success=True", repr(success_result))
        self.assertIn("vision_quartz", repr(success_result))

        fail_result = ClickResult(
            success=False,
            method=ClickMethod.FAILED,
            error_message="Element not found"
        )
        self.assertIn("success=False", repr(fail_result))
        self.assertIn("Element not found", repr(fail_result))


class TestClickHelperAppleScript(unittest.TestCase):
    """Test AppleScript click functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch subprocess.run for AppleScript tests
        self.subprocess_patcher = patch('subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.subprocess_patcher.stop()

    def test_applescript_click_success(self):
        """Test successful AppleScript click."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod

        # Mock successful AppleScript execution
        self.mock_subprocess.return_value = MagicMock(returncode=0)

        helper = ClickHelper(enable_verification=False)

        # Mock vision/screenshot to not be available
        with patch.object(helper, '_get_vision_finder', return_value=None):
            with patch.object(helper, '_get_screenshot_capture', return_value=None):
                result = helper.click_element(
                    app_name="Unity",
                    element_description="Build",
                    vision_fallback=False
                )

        self.assertTrue(result.success)
        self.assertEqual(result.method, ClickMethod.APPLESCRIPT)
        self.assertTrue(result.applescript_tried)
        self.assertFalse(result.vision_tried)

    def test_applescript_click_failure_no_fallback(self):
        """Test AppleScript failure without vision fallback."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod

        # Mock failed AppleScript execution
        self.mock_subprocess.return_value = MagicMock(returncode=1)

        helper = ClickHelper(enable_verification=False)

        result = helper.click_element(
            app_name="Unity",
            element_description="NonexistentButton",
            vision_fallback=False
        )

        self.assertFalse(result.success)
        self.assertEqual(result.method, ClickMethod.FAILED)
        self.assertTrue(result.applescript_tried)
        self.assertFalse(result.vision_tried)

    def test_applescript_with_window_name(self):
        """Test AppleScript click with window name specified."""
        from agents.computer_use.click_helper import ClickHelper

        self.mock_subprocess.return_value = MagicMock(returncode=0)

        helper = ClickHelper(enable_verification=False)

        with patch.object(helper, '_get_vision_finder', return_value=None):
            with patch.object(helper, '_get_screenshot_capture', return_value=None):
                result = helper.click_element(
                    app_name="Unity",
                    element_description="Apply",
                    window_name="Build Settings",
                    vision_fallback=False
                )

        self.assertTrue(result.success)
        # Verify the AppleScript included the window name
        call_args = self.mock_subprocess.call_args[0][0]
        script = call_args[2]  # The -e argument value
        self.assertIn("Build Settings", script)


class TestClickHelperVisionFallback(unittest.TestCase):
    """Test vision-based fallback functionality."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.subprocess_patcher = patch('subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()

        # Default to failed AppleScript to trigger fallback
        self.mock_subprocess.return_value = MagicMock(returncode=1)

    def tearDown(self):
        """Clean up patches."""
        self.subprocess_patcher.stop()

    def test_vision_fallback_success(self):
        """Test successful vision-based fallback."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod

        helper = ClickHelper(enable_verification=False)

        # Create mock vision finder and screenshot capture
        mock_vision_finder = MagicMock()
        mock_vision_finder.find_element.return_value = MockElementLocation(
            x=100,
            y=200,
            confidence=0.95,
            description="Build button"
        )

        mock_screenshot_capture = MagicMock()
        mock_screenshot_capture.capture_all_displays.return_value = MockScreenshotResult(
            image_bytes=b"fake_image_data",
            width=1920,
            height=1080,
            scale_factor=1.0
        )
        mock_screenshot_capture.screenshot_coords_to_screen.return_value = (100, 200)

        # Patch QUARTZ_AVAILABLE and Quartz for mouse events
        with patch('agents.computer_use.click_helper.QUARTZ_AVAILABLE', True):
            with patch.dict('sys.modules', {'Quartz': MockQuartz, 'Quartz.CoreGraphics': MockCoreGraphics}):
                with patch.object(helper, '_get_vision_finder', return_value=mock_vision_finder):
                    with patch.object(helper, '_get_screenshot_capture', return_value=mock_screenshot_capture):
                        with patch.object(helper, '_click_at_coordinates', return_value=True):
                            result = helper.click_element(
                                app_name="Unity",
                                element_description="Build button",
                                vision_fallback=True
                            )

        self.assertTrue(result.success)
        self.assertEqual(result.method, ClickMethod.VISION_QUARTZ)
        self.assertTrue(result.applescript_tried)
        self.assertTrue(result.vision_tried)
        self.assertEqual(result.x, 100)
        self.assertEqual(result.y, 200)
        self.assertEqual(result.confidence, 0.95)

    def test_vision_fallback_element_not_found(self):
        """Test vision fallback when element is not found."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod, QUARTZ_AVAILABLE

        helper = ClickHelper(enable_verification=False)

        # Vision finder returns None (element not found)
        mock_vision_finder = MagicMock()
        mock_vision_finder.find_element.return_value = None

        mock_screenshot_capture = MagicMock()
        mock_screenshot_capture.capture_all_displays.return_value = MockScreenshotResult(
            image_bytes=b"fake_image_data",
            width=1920,
            height=1080
        )

        # Patch QUARTZ_AVAILABLE to allow vision fallback path
        with patch('agents.computer_use.click_helper.QUARTZ_AVAILABLE', True):
            with patch.object(helper, '_get_vision_finder', return_value=mock_vision_finder):
                with patch.object(helper, '_get_screenshot_capture', return_value=mock_screenshot_capture):
                    result = helper.click_element(
                        app_name="Unity",
                        element_description="NonexistentElement",
                        vision_fallback=True
                    )

        self.assertFalse(result.success)
        self.assertEqual(result.method, ClickMethod.FAILED)
        self.assertIsNotNone(result.error_message)
        self.assertIn("not found", result.error_message or "")

    def test_vision_fallback_low_confidence(self):
        """Test vision fallback when confidence is below threshold."""
        from agents.computer_use.click_helper import ClickHelper

        # Create helper with high confidence threshold
        helper = ClickHelper(
            enable_verification=False,
            min_vision_confidence=0.9
        )

        # Vision finder returns low-confidence result
        mock_vision_finder = MagicMock()
        mock_vision_finder.find_element.return_value = None  # Should be filtered by confidence

        mock_screenshot_capture = MagicMock()
        mock_screenshot_capture.capture_all_displays.return_value = MockScreenshotResult(
            image_bytes=b"fake_image_data",
            width=1920,
            height=1080
        )

        with patch.object(helper, '_get_vision_finder', return_value=mock_vision_finder):
            with patch.object(helper, '_get_screenshot_capture', return_value=mock_screenshot_capture):
                result = helper.click_element(
                    app_name="Unity",
                    element_description="UnclearElement",
                    vision_fallback=True
                )

        self.assertFalse(result.success)


class TestClickHelperCoordinates(unittest.TestCase):
    """Test direct coordinate clicking."""

    def test_click_at_coordinates(self):
        """Test clicking at specific coordinates."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod

        helper = ClickHelper(enable_verification=False)

        # Patch QUARTZ_AVAILABLE to allow coordinate clicking
        with patch('agents.computer_use.click_helper.QUARTZ_AVAILABLE', True):
            with patch.object(helper, '_click_at_coordinates', return_value=True):
                result = helper.click_at(x=500, y=300)

        self.assertTrue(result.success)
        self.assertEqual(result.method, ClickMethod.COORDINATES)
        self.assertEqual(result.x, 500)
        self.assertEqual(result.y, 300)

    def test_double_click_at_coordinates(self):
        """Test double-clicking at specific coordinates."""
        from agents.computer_use.click_helper import ClickHelper, ClickMethod

        helper = ClickHelper(enable_verification=False)

        # Patch QUARTZ_AVAILABLE to allow coordinate clicking
        with patch('agents.computer_use.click_helper.QUARTZ_AVAILABLE', True):
            with patch.object(helper, '_double_click_at_coordinates', return_value=True):
                result = helper.double_click_at(x=600, y=400)

        self.assertTrue(result.success)
        self.assertEqual(result.method, ClickMethod.COORDINATES)
        self.assertEqual(result.x, 600)
        self.assertEqual(result.y, 400)


class TestClickHelperVerification(unittest.TestCase):
    """Test before/after screenshot verification."""

    def test_verification_screenshots_captured(self):
        """Test that verification screenshots are captured when enabled."""
        from agents.computer_use.click_helper import ClickHelper

        # Mock subprocess for AppleScript
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)

            helper = ClickHelper(enable_verification=True)

            # Mock screenshot capture
            mock_capture = MagicMock()
            mock_capture.capture_all_displays.return_value = MockScreenshotResult(
                image_bytes=b"screenshot_data",
                width=1920,
                height=1080
            )

            with patch.object(helper, '_get_screenshot_capture', return_value=mock_capture):
                with patch.object(helper, '_get_vision_finder', return_value=None):
                    result = helper.click_element(
                        app_name="Unity",
                        element_description="Build",
                        vision_fallback=False,
                        capture_verification=True
                    )

            self.assertTrue(result.success)
            self.assertEqual(result.before_screenshot, b"screenshot_data")
            self.assertEqual(result.after_screenshot, b"screenshot_data")

    def test_verification_disabled(self):
        """Test that no screenshots are captured when verification disabled."""
        from agents.computer_use.click_helper import ClickHelper

        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)

            helper = ClickHelper(enable_verification=False)

            with patch.object(helper, '_get_vision_finder', return_value=None):
                with patch.object(helper, '_get_screenshot_capture', return_value=None):
                    result = helper.click_element(
                        app_name="Unity",
                        element_description="Build",
                        vision_fallback=False,
                        capture_verification=True  # Should be ignored
                    )

            self.assertTrue(result.success)
            self.assertIsNone(result.before_screenshot)
            self.assertIsNone(result.after_screenshot)


class TestConvenienceFunction(unittest.TestCase):
    """Test the convenience function."""

    def test_click_with_vision_fallback_function(self):
        """Test the click_with_vision_fallback convenience function."""
        from agents.computer_use.click_helper import click_with_vision_fallback

        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)

            # The function should work without raising
            result = click_with_vision_fallback(
                app_name="Unity",
                element_description="Build",
                enable_verification=False
            )

            self.assertTrue(result.success)


class TestUnityAgentIntegration(unittest.TestCase):
    """Test integration with UnityAgent."""

    def test_unity_agent_click_element_method(self):
        """Test UnityAgent.click_element method."""
        from agents.computer_use.unity import UnityAgent

        agent = UnityAgent(enable_vision_fallback=True)

        with patch('subprocess.run') as mock_subprocess:
            # Mock Unity detection
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="12345"
            )

            # Test click_element exists and returns correct type
            result = agent.click_element(
                element_description="Build",
                vision_fallback=False
            )

            # Result should have the expected attributes
            self.assertIsNotNone(result)
            self.assertIsNotNone(result.success)
            self.assertIsNotNone(result.method)

    def test_unity_agent_vision_fallback_disabled(self):
        """Test UnityAgent with vision fallback disabled."""
        from agents.computer_use.unity import UnityAgent

        agent = UnityAgent(enable_vision_fallback=False)

        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=1)

            # _click_button should not try vision fallback
            result = agent._click_button(
                button_name="NonexistentButton"
            )

            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
