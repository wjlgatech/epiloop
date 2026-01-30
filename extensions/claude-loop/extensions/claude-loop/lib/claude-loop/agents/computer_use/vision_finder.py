#!/usr/bin/env python3
"""
vision_finder.py - Vision-based UI element detection using Claude Vision API

This module provides UI element detection capabilities using Claude's
vision API to locate elements in screenshots based on natural language
descriptions.

Usage:
    from agents.computer_use.vision_finder import VisionElementFinder

    finder = VisionElementFinder()
    result = finder.find_element(screenshot_bytes, "the 'Build' button in the toolbar")
    if result:
        print(f"Found at ({result.x}, {result.y}) with confidence {result.confidence}")
"""

import base64
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# Try to import anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class ElementLocation:
    """Result of a vision-based element search."""
    x: int  # X coordinate of element center
    y: int  # Y coordinate of element center
    confidence: float  # Confidence score (0.0 to 1.0)
    description: str  # Description of what was found
    bounding_box: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2) if available
    element_type: Optional[str] = None  # Type of UI element (button, text, icon, etc.)

    def __repr__(self) -> str:
        return f"ElementLocation(x={self.x}, y={self.y}, confidence={self.confidence:.2f})"


@dataclass
class APIUsageRecord:
    """Record of a single API call for cost tracking."""
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    model: str
    cache_hit: bool = False
    query_description: str = ""

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on Claude API pricing (approximate)."""
        # Pricing as of early 2024 for Claude 3 Sonnet vision
        # Input: $3 per million tokens, Output: $15 per million tokens
        # Image tokens vary by size, approximating here
        input_cost = (self.input_tokens / 1_000_000) * 3.0
        output_cost = (self.output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


@dataclass
class APIUsageStats:
    """Aggregate statistics for API usage."""
    total_calls: int = 0
    cache_hits: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_estimated_cost_usd: float = 0.0
    records: List[APIUsageRecord] = field(default_factory=list)

    def add_record(self, record: APIUsageRecord) -> None:
        """Add a usage record and update totals."""
        self.records.append(record)
        self.total_calls += 1
        if record.cache_hit:
            self.cache_hits += 1
        self.total_input_tokens += record.input_tokens
        self.total_output_tokens += record.output_tokens
        self.total_estimated_cost_usd += record.estimated_cost_usd

    @property
    def cache_hit_rate(self) -> float:
        """Return cache hit rate as a percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.cache_hits / self.total_calls) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_calls": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate_percent": self.cache_hit_rate,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_estimated_cost_usd": self.total_estimated_cost_usd,
        }


class VisionElementFinder:
    """
    Finds UI elements in screenshots using Claude Vision API.

    This class provides:
    - Natural language element search in screenshots
    - Caching of results for repeated queries on same screenshot
    - API usage tracking for cost monitoring
    - Confidence-based filtering
    """

    # Minimum confidence threshold to return a result
    DEFAULT_MIN_CONFIDENCE = 0.7

    # Default model for vision tasks
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    # Cache TTL in seconds (default: 5 minutes)
    DEFAULT_CACHE_TTL = 300

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        enable_caching: bool = True,
    ):
        """
        Initialize the VisionElementFinder.

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

        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "API key required. Provide api_key parameter or set ANTHROPIC_API_KEY environment variable."
            )

        self._model = model or self.DEFAULT_MODEL
        self._min_confidence = min_confidence
        self._cache_ttl = cache_ttl
        self._enable_caching = enable_caching

        # Initialize client
        self._client = anthropic.Anthropic(api_key=self._api_key)

        # Cache: key is (image_hash, query) -> (result, timestamp)
        self._cache: Dict[str, Tuple[Optional[ElementLocation], float]] = {}

        # Usage tracking
        self._usage_stats = APIUsageStats()

    def find_element(
        self,
        screenshot_bytes: bytes,
        element_description: str,
        screenshot_width: Optional[int] = None,
        screenshot_height: Optional[int] = None,
    ) -> Optional[ElementLocation]:
        """
        Find a UI element in a screenshot based on natural language description.

        Args:
            screenshot_bytes: PNG image bytes of the screenshot.
            element_description: Natural language description of the element to find.
                Examples: "the Build button", "File menu", "close button in top right"
            screenshot_width: Width of screenshot (for coordinate validation).
            screenshot_height: Height of screenshot (for coordinate validation).

        Returns:
            ElementLocation if found with sufficient confidence, None otherwise.
        """
        # Check cache first
        cache_key = self._get_cache_key(screenshot_bytes, element_description)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            # Record cache hit
            self._usage_stats.add_record(APIUsageRecord(
                timestamp=datetime.now(),
                input_tokens=0,
                output_tokens=0,
                model=self._model,
                cache_hit=True,
                query_description=element_description,
            ))
            return cached_result

        # Call Vision API
        result = self._call_vision_api(
            screenshot_bytes,
            element_description,
            screenshot_width,
            screenshot_height,
        )

        # Cache result
        if self._enable_caching:
            self._cache[cache_key] = (result, time.time())

        return result

    def find_all_elements(
        self,
        screenshot_bytes: bytes,
        element_description: str,
        max_results: int = 5,
    ) -> List[ElementLocation]:
        """
        Find all matching UI elements in a screenshot.

        Args:
            screenshot_bytes: PNG image bytes of the screenshot.
            element_description: Natural language description of the elements to find.
            max_results: Maximum number of results to return.

        Returns:
            List of ElementLocation objects, sorted by confidence.
        """
        # Similar to find_element but asks for multiple results
        # Note: caching multiple results is less useful due to varying max_results
        # For now, just call the API
        results = self._call_vision_api_multi(
            screenshot_bytes,
            element_description,
            max_results,
        )

        return results

    def get_usage_stats(self) -> APIUsageStats:
        """Get API usage statistics."""
        return self._usage_stats

    def reset_usage_stats(self) -> None:
        """Reset API usage statistics."""
        self._usage_stats = APIUsageStats()

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._cache.clear()

    def set_min_confidence(self, threshold: float) -> None:
        """Set the minimum confidence threshold."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self._min_confidence = threshold

    def _get_cache_key(self, screenshot_bytes: bytes, query: str) -> str:
        """Generate a cache key from screenshot hash and query."""
        image_hash = hashlib.md5(screenshot_bytes).hexdigest()
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{image_hash}:{query_hash}"

    def _get_from_cache(self, cache_key: str) -> Optional[ElementLocation]:
        """Get a result from cache if valid."""
        if not self._enable_caching:
            return None

        if cache_key not in self._cache:
            return None

        result, timestamp = self._cache[cache_key]

        # Check TTL
        if time.time() - timestamp > self._cache_ttl:
            del self._cache[cache_key]
            return None

        return result

    def _call_vision_api(
        self,
        screenshot_bytes: bytes,
        element_description: str,
        screenshot_width: Optional[int],
        screenshot_height: Optional[int],
    ) -> Optional[ElementLocation]:
        """Call Claude Vision API to find an element."""
        # Encode image as base64
        image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build the prompt
        prompt = self._build_element_find_prompt(
            element_description,
            screenshot_width,
            screenshot_height,
        )

        # Call API
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

            # Record usage
            self._usage_stats.add_record(APIUsageRecord(
                timestamp=datetime.now(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self._model,
                cache_hit=False,
                query_description=element_description,
            ))

            # Parse response
            return self._parse_element_response(response, element_description)

        except anthropic.APIError as e:
            # Log error but don't crash
            print(f"Vision API error: {e}")
            return None

    def _call_vision_api_multi(
        self,
        screenshot_bytes: bytes,
        element_description: str,
        max_results: int,
    ) -> List[ElementLocation]:
        """Call Claude Vision API to find multiple elements."""
        # Encode image as base64
        image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build the prompt for multiple results
        prompt = self._build_multi_element_find_prompt(element_description, max_results)

        # Call API
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
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

            # Record usage
            self._usage_stats.add_record(APIUsageRecord(
                timestamp=datetime.now(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self._model,
                cache_hit=False,
                query_description=f"MULTI:{element_description}",
            ))

            # Parse response
            return self._parse_multi_element_response(response, element_description)

        except anthropic.APIError as e:
            print(f"Vision API error: {e}")
            return []

    def _build_element_find_prompt(
        self,
        element_description: str,
        screenshot_width: Optional[int],
        screenshot_height: Optional[int],
    ) -> str:
        """Build the prompt for finding a single element."""
        size_info = ""
        if screenshot_width and screenshot_height:
            size_info = f"The screenshot is {screenshot_width}x{screenshot_height} pixels. "

        return f"""Analyze this screenshot and find the UI element described as: "{element_description}"

{size_info}Respond with a JSON object containing:
- "found": true/false - whether the element was found
- "x": integer - X coordinate of the element's center (in pixels from left)
- "y": integer - Y coordinate of the element's center (in pixels from top)
- "confidence": float - confidence score from 0.0 to 1.0
- "description": string - brief description of what you found
- "element_type": string - type of UI element (button, text, icon, menu, input, checkbox, etc.)
- "bounding_box": [x1, y1, x2, y2] - optional bounding box coordinates

If the element is not found, set "found" to false and explain why in "description".

Important:
- Coordinates should be in pixels, with (0,0) at the top-left corner
- Be precise about the element's center location
- Only report high confidence if you're certain about the location
- Consider partial matches but lower the confidence accordingly

Respond with ONLY the JSON object, no other text."""

    def _build_multi_element_find_prompt(
        self,
        element_description: str,
        max_results: int,
    ) -> str:
        """Build the prompt for finding multiple elements."""
        return f"""Analyze this screenshot and find ALL UI elements matching: "{element_description}"

Return up to {max_results} matches.

Respond with a JSON object containing:
- "count": integer - number of elements found
- "elements": array of objects, each containing:
  - "x": integer - X coordinate of the element's center
  - "y": integer - Y coordinate of the element's center
  - "confidence": float - confidence score from 0.0 to 1.0
  - "description": string - brief description of what you found
  - "element_type": string - type of UI element

Sort elements by confidence (highest first).

Respond with ONLY the JSON object, no other text."""

    def _parse_element_response(
        self,
        response: Any,
        original_query: str,
    ) -> Optional[ElementLocation]:
        """Parse the API response to extract element location."""
        try:
            # Get text content from response
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            # Parse JSON from response
            # Handle potential markdown code blocks
            json_str = text_content.strip()
            if json_str.startswith("```"):
                # Extract JSON from code block
                json_str = re.sub(r"```(?:json)?\n?", "", json_str)
                json_str = json_str.strip()

            data = json.loads(json_str)

            # Check if element was found
            if not data.get("found", False):
                return None

            # Extract coordinates and confidence
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            confidence = float(data.get("confidence", 0.0))

            # Apply confidence threshold
            if confidence < self._min_confidence:
                return None

            # Parse optional bounding box
            bounding_box: Optional[Tuple[int, int, int, int]] = None
            if "bounding_box" in data and data["bounding_box"]:
                bbox = data["bounding_box"]
                if len(bbox) == 4:
                    bounding_box = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))

            return ElementLocation(
                x=x,
                y=y,
                confidence=confidence,
                description=data.get("description", original_query),
                bounding_box=bounding_box,
                element_type=data.get("element_type"),
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"Failed to parse vision response: {e}")
            return None

    def _parse_multi_element_response(
        self,
        response: Any,
        original_query: str,
    ) -> List[ElementLocation]:
        """Parse the API response to extract multiple element locations."""
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

            results = []
            for elem in data.get("elements", []):
                confidence = float(elem.get("confidence", 0.0))

                # Apply confidence threshold
                if confidence < self._min_confidence:
                    continue

                results.append(ElementLocation(
                    x=int(elem.get("x", 0)),
                    y=int(elem.get("y", 0)),
                    confidence=confidence,
                    description=elem.get("description", original_query),
                    element_type=elem.get("element_type"),
                ))

            return results

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"Failed to parse vision response: {e}")
            return []


# Convenience functions

def find_element(
    screenshot_bytes: bytes,
    element_description: str,
    min_confidence: float = VisionElementFinder.DEFAULT_MIN_CONFIDENCE,
) -> Optional[ElementLocation]:
    """
    Find a UI element in a screenshot.

    Args:
        screenshot_bytes: PNG image bytes.
        element_description: Natural language description of the element.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementLocation if found, None otherwise.
    """
    finder = VisionElementFinder(min_confidence=min_confidence)
    return finder.find_element(screenshot_bytes, element_description)


def find_element_with_retry(
    screenshot_bytes: bytes,
    element_description: str,
    max_retries: int = 3,
    min_confidence: float = VisionElementFinder.DEFAULT_MIN_CONFIDENCE,
) -> Optional[ElementLocation]:
    """
    Find a UI element with retry logic.

    Args:
        screenshot_bytes: PNG image bytes.
        element_description: Natural language description.
        max_retries: Maximum number of attempts.
        min_confidence: Minimum confidence threshold.

    Returns:
        ElementLocation if found, None otherwise.
    """
    finder = VisionElementFinder(min_confidence=min_confidence, enable_caching=False)

    for attempt in range(max_retries):
        result = finder.find_element(screenshot_bytes, element_description)
        if result is not None:
            return result

        # Could add increasing delays between retries
        if attempt < max_retries - 1:
            time.sleep(0.5 * (attempt + 1))

    return None
