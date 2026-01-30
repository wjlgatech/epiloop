#!/usr/bin/env python3
"""
vision_detector.py - Vision API Integration for Element Detection

This module provides UI element detection using Claude's Vision API.
It wraps the VisionElementFinder functionality and provides additional
convenience methods specific to the vision_detector interface.

Usage:
    from agents.computer_use.vision_detector import VisionDetector

    detector = VisionDetector()
    result = detector.find_element(screenshot_bytes, "the 'Build' button")
    if result:
        print(f"Found at ({result.x}, {result.y})")
        if result.bounding_box:
            x, y, w, h = result.bounding_box
            print(f"Bounding box: {x}, {y}, {w}x{h}")

    # Get element state
    state = detector.get_element_state(screenshot_bytes, "the 'Build' button")
    if state:
        print(f"Button is {'enabled' if state.enabled else 'disabled'}")
        print(f"Button state: {state.button_state}")
"""

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Union

# Re-export core classes from vision_finder
from .vision_finder import (
    VisionElementFinder,
    ElementLocation,
    APIUsageRecord,
    APIUsageStats,
    ANTHROPIC_AVAILABLE,
)

# Try to import anthropic for state detection API calls
try:
    import anthropic  # type: ignore
except ImportError:
    pass  # Already handled by ANTHROPIC_AVAILABLE flag


# ============================================================================
# Element State Enums and Types
# ============================================================================

class ButtonState(Enum):
    """Possible states for a button element."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PRESSED = "pressed"
    HOVER = "hover"
    FOCUSED = "focused"
    UNKNOWN = "unknown"


class CheckboxState(Enum):
    """Possible states for a checkbox element."""
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    INDETERMINATE = "indeterminate"
    UNKNOWN = "unknown"


class ProgressState(Enum):
    """Possible states for a progress indicator."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    INDETERMINATE = "indeterminate"
    UNKNOWN = "unknown"


@dataclass
class ElementState:
    """
    Structured representation of a UI element's state.

    This dataclass captures various aspects of element state including:
    - Basic state (enabled/disabled, visible)
    - Button-specific state (pressed, hover)
    - Checkbox state (checked/unchecked)
    - Text content (for text fields, labels, dropdowns)
    - Progress information (for progress bars)
    - Error/status messages
    """
    # Basic element info
    element_type: str
    description: str
    confidence: float

    # Visibility and enabled state
    visible: bool = True
    enabled: Optional[bool] = None

    # Button-specific state
    button_state: Optional[ButtonState] = None

    # Checkbox-specific state
    checkbox_state: Optional[CheckboxState] = None

    # Text content (for text fields, labels, dropdowns)
    text_content: Optional[str] = None
    placeholder_text: Optional[str] = None

    # Dropdown-specific state
    dropdown_selected: Optional[str] = None
    dropdown_options: Optional[List[str]] = None
    dropdown_open: Optional[bool] = None

    # Progress indicator state
    progress_state: Optional[ProgressState] = None
    progress_value: Optional[float] = None  # 0.0 to 1.0
    progress_text: Optional[str] = None  # e.g., "50%" or "Building..."

    # Error/status text
    error_message: Optional[str] = None
    status_text: Optional[str] = None
    warning_message: Optional[str] = None

    # Position info (optional, may be included from detection)
    x: Optional[int] = None
    y: Optional[int] = None
    bounding_box: Optional["BoundingBox"] = None

    # Timestamp when state was captured
    captured_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result: Dict[str, Any] = {
            "element_type": self.element_type,
            "description": self.description,
            "confidence": self.confidence,
            "visible": self.visible,
        }

        # Add optional fields if set
        if self.enabled is not None:
            result["enabled"] = self.enabled
        if self.button_state is not None:
            result["button_state"] = self.button_state.value
        if self.checkbox_state is not None:
            result["checkbox_state"] = self.checkbox_state.value
        if self.text_content is not None:
            result["text_content"] = self.text_content
        if self.placeholder_text is not None:
            result["placeholder_text"] = self.placeholder_text
        if self.dropdown_selected is not None:
            result["dropdown_selected"] = self.dropdown_selected
        if self.dropdown_options is not None:
            result["dropdown_options"] = self.dropdown_options
        if self.dropdown_open is not None:
            result["dropdown_open"] = self.dropdown_open
        if self.progress_state is not None:
            result["progress_state"] = self.progress_state.value
        if self.progress_value is not None:
            result["progress_value"] = self.progress_value
        if self.progress_text is not None:
            result["progress_text"] = self.progress_text
        if self.error_message is not None:
            result["error_message"] = self.error_message
        if self.status_text is not None:
            result["status_text"] = self.status_text
        if self.warning_message is not None:
            result["warning_message"] = self.warning_message
        if self.x is not None:
            result["x"] = self.x
        if self.y is not None:
            result["y"] = self.y
        if self.bounding_box is not None:
            result["bounding_box"] = self.bounding_box.to_dict()

        result["captured_at"] = self.captured_at.isoformat()
        return result

    @property
    def is_enabled(self) -> bool:
        """Check if element is enabled (convenience property)."""
        return self.enabled is True

    @property
    def is_disabled(self) -> bool:
        """Check if element is disabled (convenience property)."""
        return self.enabled is False

    @property
    def is_checked(self) -> bool:
        """Check if checkbox is checked (convenience property)."""
        return self.checkbox_state == CheckboxState.CHECKED

    @property
    def is_unchecked(self) -> bool:
        """Check if checkbox is unchecked (convenience property)."""
        return self.checkbox_state == CheckboxState.UNCHECKED

    @property
    def has_error(self) -> bool:
        """Check if element has an error state."""
        return self.error_message is not None or self.progress_state == ProgressState.ERROR


# ============================================================================
# Bounding Box
# ============================================================================

@dataclass
class BoundingBox:
    """Bounding box representation with width/height instead of x2/y2."""
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_tuple(cls, bbox: Tuple[int, int, int, int]) -> 'BoundingBox':
        """Create from (x1, y1, x2, y2) tuple."""
        x1, y1, x2, y2 = bbox
        return cls(x=x1, y=y1, width=x2 - x1, height=y2 - y1)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary {x, y, width, height}."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    def center(self) -> Tuple[int, int]:
        """Get center coordinates of bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class DetectionResult:
    """
    Result from vision detection, with convenient bounding box access.

    Provides the same data as ElementLocation but with additional
    convenience methods and the bounding box in {x, y, width, height} format.
    """
    x: int  # Center X coordinate
    y: int  # Center Y coordinate
    confidence: float
    description: str
    element_type: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None

    @classmethod
    def from_element_location(cls, elem: ElementLocation) -> 'DetectionResult':
        """Create from an ElementLocation."""
        bbox = None
        if elem.bounding_box:
            bbox = BoundingBox.from_tuple(elem.bounding_box)

        return cls(
            x=elem.x,
            y=elem.y,
            confidence=elem.confidence,
            description=elem.description,
            element_type=elem.element_type,
            bounding_box=bbox,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "description": self.description,
            "element_type": self.element_type,
        }
        if self.bounding_box:
            result["bounding_box"] = self.bounding_box.to_dict()
        return result


class VisionDetector:
    """
    Vision-based UI element detector using Claude Vision API.

    This class provides:
    - Natural language element search in screenshots
    - Support for buttons, text fields, checkboxes, labels, icons
    - Response caching to reduce API costs
    - Token usage logging for cost tracking
    - Graceful error handling with helpful messages

    Example:
        detector = VisionDetector()

        # Find a button by text content
        result = detector.find_element(screenshot, "the 'Fix All' button")

        # Find an element by visual appearance
        result = detector.find_element(screenshot, "red warning icon near the console")

        # Get usage stats
        stats = detector.get_usage_stats()
        print(f"API calls: {stats.total_calls}, Cost: ${stats.total_estimated_cost_usd:.4f}")
    """

    # Element type constants for convenience
    ELEMENT_BUTTON = "button"
    ELEMENT_TEXT_FIELD = "input"
    ELEMENT_CHECKBOX = "checkbox"
    ELEMENT_LABEL = "text"
    ELEMENT_ICON = "icon"
    ELEMENT_MENU = "menu"
    ELEMENT_DROPDOWN = "dropdown"

    # Default model for state detection queries
    DEFAULT_STATE_MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        min_confidence: float = 0.7,
        cache_ttl: int = 300,
        enable_caching: bool = True,
    ):
        """
        Initialize the VisionDetector.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Model to use for vision queries. Defaults to claude-sonnet-4-20250514.
            min_confidence: Minimum confidence threshold (0.0-1.0) to return results.
            cache_ttl: Cache time-to-live in seconds.
            enable_caching: Whether to enable result caching.
        """
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "anthropic package not available. Install with: pip install anthropic"
            )

        self._finder = VisionElementFinder(
            api_key=api_key,
            model=model,
            min_confidence=min_confidence,
            cache_ttl=cache_ttl,
            enable_caching=enable_caching,
        )

        # Store config for state detection
        self._model = model or self.DEFAULT_STATE_MODEL
        self._min_confidence = min_confidence
        self._cache_ttl = cache_ttl
        self._enable_caching = enable_caching

        # State query cache: key is (screenshot_hash, query) -> (ElementState, timestamp)
        self._state_cache: Dict[str, Tuple[Optional[ElementState], float]] = {}

        # Get API client for direct state queries
        self._client = self._finder._client

    def find_element(
        self,
        screenshot: bytes,
        element_description: str,
        screenshot_width: Optional[int] = None,
        screenshot_height: Optional[int] = None,
    ) -> Optional[DetectionResult]:
        """
        Find a UI element in a screenshot using Claude Vision API.

        Supports finding elements by:
        - Text content: "the 'Fix All' button", "label saying 'Project Setup'"
        - Visual appearance: "red X icon", "blue toggle switch"
        - Position context: "close button in top right", "menu bar"
        - Element type: "checkbox next to 'Enable VR'", "dropdown for Build Target"

        Args:
            screenshot: PNG image bytes of the screenshot.
            element_description: Natural language description of the element.
            screenshot_width: Optional width for coordinate validation.
            screenshot_height: Optional height for coordinate validation.

        Returns:
            DetectionResult with bounding box if found, None otherwise.
            Returns None if element not found or confidence below threshold.
        """
        result = self._finder.find_element(
            screenshot_bytes=screenshot,
            element_description=element_description,
            screenshot_width=screenshot_width,
            screenshot_height=screenshot_height,
        )

        if result is None:
            return None

        return DetectionResult.from_element_location(result)

    def find_button(
        self,
        screenshot: bytes,
        button_text: str,
    ) -> Optional[DetectionResult]:
        """
        Find a button by its text label.

        Args:
            screenshot: PNG image bytes of the screenshot.
            button_text: The text displayed on the button.

        Returns:
            DetectionResult if found, None otherwise.
        """
        description = f"button labeled '{button_text}'"
        return self.find_element(screenshot, description)

    def find_text_field(
        self,
        screenshot: bytes,
        label_or_placeholder: str,
    ) -> Optional[DetectionResult]:
        """
        Find a text input field by its label or placeholder text.

        Args:
            screenshot: PNG image bytes of the screenshot.
            label_or_placeholder: The label next to the field or placeholder text.

        Returns:
            DetectionResult if found, None otherwise.
        """
        description = f"text input field for '{label_or_placeholder}'"
        return self.find_element(screenshot, description)

    def find_checkbox(
        self,
        screenshot: bytes,
        label: str,
    ) -> Optional[DetectionResult]:
        """
        Find a checkbox by its label.

        Args:
            screenshot: PNG image bytes of the screenshot.
            label: The label text next to the checkbox.

        Returns:
            DetectionResult if found, None otherwise.
        """
        description = f"checkbox with label '{label}'"
        return self.find_element(screenshot, description)

    def find_label(
        self,
        screenshot: bytes,
        text: str,
    ) -> Optional[DetectionResult]:
        """
        Find a text label.

        Args:
            screenshot: PNG image bytes of the screenshot.
            text: The text of the label to find.

        Returns:
            DetectionResult if found, None otherwise.
        """
        description = f"text label saying '{text}'"
        return self.find_element(screenshot, description)

    def find_icon(
        self,
        screenshot: bytes,
        icon_description: str,
    ) -> Optional[DetectionResult]:
        """
        Find an icon by its visual description.

        Args:
            screenshot: PNG image bytes of the screenshot.
            icon_description: Visual description of the icon (e.g., "red warning", "gear").

        Returns:
            DetectionResult if found, None otherwise.
        """
        description = f"{icon_description} icon"
        return self.find_element(screenshot, description)

    def find_all_elements(
        self,
        screenshot: bytes,
        element_description: str,
        max_results: int = 5,
    ) -> List[DetectionResult]:
        """
        Find all matching UI elements in a screenshot.

        Args:
            screenshot: PNG image bytes of the screenshot.
            element_description: Natural language description.
            max_results: Maximum number of results to return.

        Returns:
            List of DetectionResult objects, sorted by confidence.
        """
        results = self._finder.find_all_elements(
            screenshot_bytes=screenshot,
            element_description=element_description,
            max_results=max_results,
        )

        return [DetectionResult.from_element_location(r) for r in results]

    def get_usage_stats(self) -> APIUsageStats:
        """
        Get API usage statistics.

        Returns:
            APIUsageStats with call counts, token usage, and cost estimates.
        """
        return self._finder.get_usage_stats()

    def reset_usage_stats(self) -> None:
        """Reset API usage statistics."""
        self._finder.reset_usage_stats()

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._finder.clear_cache()

    def set_min_confidence(self, threshold: float) -> None:
        """
        Set the minimum confidence threshold.

        Args:
            threshold: Value between 0.0 and 1.0
        """
        self._finder.set_min_confidence(threshold)

    # ========================================================================
    # Element State Detection Methods
    # ========================================================================

    def get_element_state(
        self,
        screenshot: bytes,
        element_description: str,
    ) -> Optional[ElementState]:
        """
        Get the state of a UI element in a screenshot.

        This method analyzes the visual state of a UI element, detecting:
        - Button states: enabled, disabled, pressed
        - Checkbox states: checked, unchecked
        - Text field contents
        - Dropdown current selection
        - Error messages and status text
        - Progress indicators

        Args:
            screenshot: PNG image bytes of the screenshot.
            element_description: Natural language description of the element.

        Returns:
            ElementState with detailed state information, or None if not found.
        """
        # Check cache first
        cache_key = self._get_state_cache_key(screenshot, element_description)
        cached_result = self._get_from_state_cache(cache_key)
        if cached_result is not None:
            return cached_result

        # Make API call for state detection
        result = self._call_state_api(screenshot, element_description)

        # Cache the result
        if self._enable_caching:
            self._state_cache[cache_key] = (result, time.time())

        return result

    def get_button_state(
        self,
        screenshot: bytes,
        button_text: str,
    ) -> Optional[ElementState]:
        """
        Get the state of a button (enabled, disabled, pressed).

        Args:
            screenshot: PNG image bytes of the screenshot.
            button_text: The text displayed on the button.

        Returns:
            ElementState with button_state field set.
        """
        description = f"button labeled '{button_text}' - determine if it is enabled, disabled, or pressed"
        return self.get_element_state(screenshot, description)

    def get_checkbox_state(
        self,
        screenshot: bytes,
        checkbox_label: str,
    ) -> Optional[ElementState]:
        """
        Get the state of a checkbox (checked, unchecked, indeterminate).

        Args:
            screenshot: PNG image bytes of the screenshot.
            checkbox_label: The label text next to the checkbox.

        Returns:
            ElementState with checkbox_state field set.
        """
        description = f"checkbox with label '{checkbox_label}' - determine if it is checked or unchecked"
        return self.get_element_state(screenshot, description)

    def get_text_field_content(
        self,
        screenshot: bytes,
        field_label: str,
    ) -> Optional[ElementState]:
        """
        Get the content of a text input field.

        Args:
            screenshot: PNG image bytes of the screenshot.
            field_label: The label next to the text field.

        Returns:
            ElementState with text_content and placeholder_text fields set.
        """
        description = f"text input field for '{field_label}' - read its current text content"
        return self.get_element_state(screenshot, description)

    def get_dropdown_selection(
        self,
        screenshot: bytes,
        dropdown_label: str,
    ) -> Optional[ElementState]:
        """
        Get the current selection of a dropdown.

        Args:
            screenshot: PNG image bytes of the screenshot.
            dropdown_label: The label for the dropdown.

        Returns:
            ElementState with dropdown_selected field set.
        """
        description = f"dropdown for '{dropdown_label}' - read its currently selected value"
        return self.get_element_state(screenshot, description)

    def get_error_message(
        self,
        screenshot: bytes,
        context: str = "",
    ) -> Optional[ElementState]:
        """
        Detect and read error messages in the screenshot.

        Args:
            screenshot: PNG image bytes of the screenshot.
            context: Optional context to narrow the search (e.g., "in the console").

        Returns:
            ElementState with error_message field set if error found.
        """
        description = f"error message or error text{' ' + context if context else ''}"
        return self.get_element_state(screenshot, description)

    def get_status_text(
        self,
        screenshot: bytes,
        context: str = "",
    ) -> Optional[ElementState]:
        """
        Read status text or messages in the screenshot.

        Args:
            screenshot: PNG image bytes of the screenshot.
            context: Optional context to narrow the search.

        Returns:
            ElementState with status_text field set.
        """
        description = f"status text or status message{' ' + context if context else ''}"
        return self.get_element_state(screenshot, description)

    def get_progress_indicator(
        self,
        screenshot: bytes,
        context: str = "",
    ) -> Optional[ElementState]:
        """
        Get the state of a progress indicator.

        Args:
            screenshot: PNG image bytes of the screenshot.
            context: Optional context (e.g., "build progress", "loading indicator").

        Returns:
            ElementState with progress_state, progress_value, and progress_text fields set.
        """
        description = f"progress indicator or progress bar{' for ' + context if context else ''}"
        return self.get_element_state(screenshot, description)

    def clear_state_cache(self) -> None:
        """Clear the state query cache."""
        self._state_cache.clear()

    # ========================================================================
    # Private Helper Methods for State Detection
    # ========================================================================

    def _get_state_cache_key(self, screenshot: bytes, query: str) -> str:
        """Generate a cache key for state queries."""
        image_hash = hashlib.md5(screenshot).hexdigest()
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"state:{image_hash}:{query_hash}"

    def _get_from_state_cache(self, cache_key: str) -> Optional[ElementState]:
        """Get a state result from cache if valid."""
        if not self._enable_caching:
            return None

        if cache_key not in self._state_cache:
            return None

        result, timestamp = self._state_cache[cache_key]

        # Check TTL
        if time.time() - timestamp > self._cache_ttl:
            del self._state_cache[cache_key]
            return None

        return result

    def _call_state_api(
        self,
        screenshot: bytes,
        element_description: str,
    ) -> Optional[ElementState]:
        """Call Claude Vision API to get element state."""
        # Encode image as base64
        image_base64 = base64.b64encode(screenshot).decode("utf-8")

        # Build the prompt for state detection
        prompt = self._build_state_detection_prompt(element_description)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Record usage via the finder's stats
            self._finder._usage_stats.add_record(APIUsageRecord(
                timestamp=datetime.now(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self._model,
                cache_hit=False,
                query_description=f"STATE:{element_description}",
            ))

            # Parse response
            return self._parse_state_response(response, element_description)

        except Exception as e:
            print(f"Vision API state detection error: {e}")
            return None

    def _build_state_detection_prompt(self, element_description: str) -> str:
        """Build the prompt for state detection."""
        return f"""Analyze this screenshot and determine the state of the UI element described as: "{element_description}"

Respond with a JSON object containing the element's state. Include all applicable fields:

Required fields:
- "found": boolean - whether the element was found
- "element_type": string - type of element (button, checkbox, input, dropdown, label, progress_bar, status_text, error_message, etc.)
- "description": string - description of what was found
- "confidence": float - confidence score 0.0 to 1.0
- "visible": boolean - whether the element is visible

For buttons, also include:
- "enabled": boolean - whether the button is enabled (clickable)
- "button_state": string - one of: "enabled", "disabled", "pressed", "hover", "focused"

For checkboxes, also include:
- "checkbox_state": string - one of: "checked", "unchecked", "indeterminate"

For text input fields, also include:
- "text_content": string - the text currently in the field (empty string if empty)
- "placeholder_text": string - placeholder text if visible and field is empty

For dropdowns, also include:
- "dropdown_selected": string - currently selected value
- "dropdown_open": boolean - whether dropdown is expanded
- "dropdown_options": array of strings - visible options if dropdown is open

For progress indicators, also include:
- "progress_state": string - one of: "not_started", "in_progress", "completed", "error", "indeterminate"
- "progress_value": float - progress percentage 0.0 to 1.0 (if determinate)
- "progress_text": string - any text shown with the progress (e.g., "50%", "Building...")

For error/status messages, also include:
- "error_message": string - error text if this is an error message
- "status_text": string - status text content
- "warning_message": string - warning text if this is a warning

Optional position fields:
- "x": integer - X coordinate of element center
- "y": integer - Y coordinate of element center
- "bounding_box": [x1, y1, x2, y2] - bounding box coordinates

If the element is not found, set "found" to false and explain in "description".

Respond with ONLY the JSON object, no other text."""

    def _parse_state_response(
        self,
        response: Any,
        original_query: str,
    ) -> Optional[ElementState]:
        """Parse the API response to extract element state."""
        try:
            # Get text content from response
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            # Parse JSON from response
            json_str = text_content.strip()
            if json_str.startswith("```"):
                json_str = re.sub(r"```(?:json)?\n?", "", json_str)
                json_str = json_str.strip()

            data = json.loads(json_str)

            # Check if element was found
            if not data.get("found", False):
                return None

            # Extract confidence and apply threshold
            confidence = float(data.get("confidence", 0.0))
            if confidence < self._min_confidence:
                return None

            # Build ElementState from response
            state = ElementState(
                element_type=data.get("element_type", "unknown"),
                description=data.get("description", original_query),
                confidence=confidence,
                visible=data.get("visible", True),
            )

            # Set enabled state
            if "enabled" in data:
                state.enabled = data["enabled"]

            # Set button state
            if "button_state" in data:
                try:
                    state.button_state = ButtonState(data["button_state"])
                except ValueError:
                    state.button_state = ButtonState.UNKNOWN

            # Set checkbox state
            if "checkbox_state" in data:
                try:
                    state.checkbox_state = CheckboxState(data["checkbox_state"])
                except ValueError:
                    state.checkbox_state = CheckboxState.UNKNOWN

            # Set text content
            if "text_content" in data:
                state.text_content = data["text_content"]
            if "placeholder_text" in data:
                state.placeholder_text = data["placeholder_text"]

            # Set dropdown state
            if "dropdown_selected" in data:
                state.dropdown_selected = data["dropdown_selected"]
            if "dropdown_open" in data:
                state.dropdown_open = data["dropdown_open"]
            if "dropdown_options" in data:
                state.dropdown_options = data["dropdown_options"]

            # Set progress state
            if "progress_state" in data:
                try:
                    state.progress_state = ProgressState(data["progress_state"])
                except ValueError:
                    state.progress_state = ProgressState.UNKNOWN
            if "progress_value" in data:
                state.progress_value = float(data["progress_value"])
            if "progress_text" in data:
                state.progress_text = data["progress_text"]

            # Set error/status messages
            if "error_message" in data:
                state.error_message = data["error_message"]
            if "status_text" in data:
                state.status_text = data["status_text"]
            if "warning_message" in data:
                state.warning_message = data["warning_message"]

            # Set position if available
            if "x" in data:
                state.x = int(data["x"])
            if "y" in data:
                state.y = int(data["y"])
            if "bounding_box" in data and data["bounding_box"]:
                bbox = data["bounding_box"]
                if len(bbox) == 4:
                    state.bounding_box = BoundingBox.from_tuple(
                        (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                    )

            return state

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"Failed to parse state response: {e}")
            return None


# Convenience functions

def find_element(
    screenshot: bytes,
    element_description: str,
    min_confidence: float = 0.7,
) -> Optional[DetectionResult]:
    """
    Find a UI element in a screenshot.

    Convenience function that creates a VisionDetector instance and
    performs a single search. For multiple searches, create a VisionDetector
    instance directly to benefit from caching.

    Args:
        screenshot: PNG image bytes of the screenshot.
        element_description: Natural language description.
        min_confidence: Minimum confidence threshold.

    Returns:
        DetectionResult if found with sufficient confidence, None otherwise.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.find_element(screenshot, element_description)


def find_button(
    screenshot: bytes,
    button_text: str,
    min_confidence: float = 0.7,
) -> Optional[DetectionResult]:
    """
    Find a button by its text label.

    Args:
        screenshot: PNG image bytes of the screenshot.
        button_text: The text displayed on the button.
        min_confidence: Minimum confidence threshold.

    Returns:
        DetectionResult if found, None otherwise.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.find_button(screenshot, button_text)


def find_all_buttons(
    screenshot: bytes,
    max_results: int = 10,
    min_confidence: float = 0.7,
) -> List[DetectionResult]:
    """
    Find all visible buttons in a screenshot.

    Args:
        screenshot: PNG image bytes of the screenshot.
        max_results: Maximum number of buttons to return.
        min_confidence: Minimum confidence threshold.

    Returns:
        List of DetectionResult objects for found buttons.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.find_all_elements(screenshot, "button", max_results)


# ============================================================================
# State Detection Convenience Functions
# ============================================================================

def get_element_state(
    screenshot: bytes,
    element_description: str,
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the state of a UI element in a screenshot.

    Convenience function for one-off state queries. For multiple queries,
    create a VisionDetector instance to benefit from caching.

    Args:
        screenshot: PNG image bytes of the screenshot.
        element_description: Natural language description of the element.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with detailed state information, or None if not found.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_element_state(screenshot, element_description)


def get_button_state(
    screenshot: bytes,
    button_text: str,
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the state of a button (enabled, disabled, pressed).

    Args:
        screenshot: PNG image bytes of the screenshot.
        button_text: The text displayed on the button.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with button_state field set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_button_state(screenshot, button_text)


def get_checkbox_state(
    screenshot: bytes,
    checkbox_label: str,
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the state of a checkbox (checked, unchecked).

    Args:
        screenshot: PNG image bytes of the screenshot.
        checkbox_label: The label text next to the checkbox.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with checkbox_state field set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_checkbox_state(screenshot, checkbox_label)


def get_text_field_content(
    screenshot: bytes,
    field_label: str,
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the content of a text input field.

    Args:
        screenshot: PNG image bytes of the screenshot.
        field_label: The label next to the text field.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with text_content field set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_text_field_content(screenshot, field_label)


def get_dropdown_selection(
    screenshot: bytes,
    dropdown_label: str,
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the current selection of a dropdown.

    Args:
        screenshot: PNG image bytes of the screenshot.
        dropdown_label: The label for the dropdown.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with dropdown_selected field set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_dropdown_selection(screenshot, dropdown_label)


def get_error_message(
    screenshot: bytes,
    context: str = "",
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Detect and read error messages in the screenshot.

    Args:
        screenshot: PNG image bytes of the screenshot.
        context: Optional context to narrow the search.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with error_message field set if found.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_error_message(screenshot, context)


def get_status_text(
    screenshot: bytes,
    context: str = "",
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Read status text or messages in the screenshot.

    Args:
        screenshot: PNG image bytes of the screenshot.
        context: Optional context to narrow the search.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with status_text field set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_status_text(screenshot, context)


def get_progress_indicator(
    screenshot: bytes,
    context: str = "",
    min_confidence: float = 0.7,
) -> Optional[ElementState]:
    """
    Get the state of a progress indicator.

    Args:
        screenshot: PNG image bytes of the screenshot.
        context: Optional context (e.g., "build progress").
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementState with progress_state and progress_value fields set.
    """
    detector = VisionDetector(min_confidence=min_confidence)
    return detector.get_progress_indicator(screenshot, context)


# Re-export availability flag
VISION_DETECTOR_AVAILABLE = ANTHROPIC_AVAILABLE

__all__ = [
    # Main class
    "VisionDetector",
    # Data classes
    "DetectionResult",
    "BoundingBox",
    # Element state classes and enums
    "ElementState",
    "ButtonState",
    "CheckboxState",
    "ProgressState",
    # Re-exported from vision_finder
    "ElementLocation",
    "APIUsageRecord",
    "APIUsageStats",
    # Element detection convenience functions
    "find_element",
    "find_button",
    "find_all_buttons",
    # State detection convenience functions
    "get_element_state",
    "get_button_state",
    "get_checkbox_state",
    "get_text_field_content",
    "get_dropdown_selection",
    "get_error_message",
    "get_status_text",
    "get_progress_indicator",
    # Availability flag
    "VISION_DETECTOR_AVAILABLE",
]
