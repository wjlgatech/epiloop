#!/usr/bin/env python3
"""
test_vision_finder.py - Tests for vision-based UI element detection

These tests verify the VisionElementFinder functionality using mocked
API responses to avoid actual API calls during testing.
"""

import base64
import hashlib
import json
import os
import pytest
import time
from dataclasses import dataclass
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

# Import the module under test
from agents.computer_use.vision_finder import (
    VisionElementFinder,
    ElementLocation,
    APIUsageRecord,
    APIUsageStats,
    find_element,
    find_element_with_retry,
    ANTHROPIC_AVAILABLE,
)


# Sample PNG image bytes (1x1 pixel transparent PNG)
SAMPLE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Another sample PNG (different hash)
SAMPLE_PNG_2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@dataclass
class MockUsage:
    """Mock usage data for API responses."""
    input_tokens: int = 1000
    output_tokens: int = 100


@dataclass
class MockContentBlock:
    """Mock content block from API response."""
    text: str


class MockResponse:
    """Mock API response."""
    def __init__(self, text: str, input_tokens: int = 1000, output_tokens: int = 100):
        self.content = [MockContentBlock(text=text)]
        self.usage = MockUsage(input_tokens=input_tokens, output_tokens=output_tokens)


def create_mock_client():
    """Create a mock Anthropic client."""
    mock_client = MagicMock()
    return mock_client


# ============================================================================
# Test ElementLocation dataclass
# ============================================================================

class TestElementLocation:
    """Tests for ElementLocation dataclass."""

    def test_basic_creation(self):
        """Test creating an ElementLocation with required fields."""
        loc = ElementLocation(
            x=100,
            y=200,
            confidence=0.95,
            description="Build button"
        )
        assert loc.x == 100
        assert loc.y == 200
        assert loc.confidence == 0.95
        assert loc.description == "Build button"
        assert loc.bounding_box is None
        assert loc.element_type is None

    def test_full_creation(self):
        """Test creating an ElementLocation with all fields."""
        loc = ElementLocation(
            x=100,
            y=200,
            confidence=0.95,
            description="Build button",
            bounding_box=(90, 190, 110, 210),
            element_type="button"
        )
        assert loc.bounding_box == (90, 190, 110, 210)
        assert loc.element_type == "button"

    def test_repr(self):
        """Test string representation."""
        loc = ElementLocation(x=100, y=200, confidence=0.95, description="test")
        assert "x=100" in repr(loc)
        assert "y=200" in repr(loc)
        assert "0.95" in repr(loc)


# ============================================================================
# Test APIUsageRecord dataclass
# ============================================================================

class TestAPIUsageRecord:
    """Tests for APIUsageRecord dataclass."""

    def test_cost_calculation(self):
        """Test estimated cost calculation."""
        from datetime import datetime
        record = APIUsageRecord(
            timestamp=datetime.now(),
            input_tokens=1_000_000,
            output_tokens=100_000,
            model="claude-sonnet-4-20250514"
        )
        # Input: $3/M * 1M = $3.00
        # Output: $15/M * 0.1M = $1.50
        # Total: $4.50
        assert record.estimated_cost_usd == pytest.approx(4.5, rel=0.01)

    def test_cache_hit_record(self):
        """Test record with cache hit."""
        from datetime import datetime
        record = APIUsageRecord(
            timestamp=datetime.now(),
            input_tokens=0,
            output_tokens=0,
            model="claude-sonnet-4-20250514",
            cache_hit=True
        )
        assert record.cache_hit is True
        assert record.estimated_cost_usd == 0.0


# ============================================================================
# Test APIUsageStats dataclass
# ============================================================================

class TestAPIUsageStats:
    """Tests for APIUsageStats dataclass."""

    def test_empty_stats(self):
        """Test default empty stats."""
        stats = APIUsageStats()
        assert stats.total_calls == 0
        assert stats.cache_hits == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_estimated_cost_usd == 0.0
        assert stats.cache_hit_rate == 0.0

    def test_add_record(self):
        """Test adding records to stats."""
        from datetime import datetime
        stats = APIUsageStats()

        record1 = APIUsageRecord(
            timestamp=datetime.now(),
            input_tokens=1000,
            output_tokens=100,
            model="claude-sonnet-4-20250514"
        )
        stats.add_record(record1)

        assert stats.total_calls == 1
        assert stats.cache_hits == 0
        assert stats.total_input_tokens == 1000
        assert stats.total_output_tokens == 100

        # Add a cache hit
        record2 = APIUsageRecord(
            timestamp=datetime.now(),
            input_tokens=0,
            output_tokens=0,
            model="claude-sonnet-4-20250514",
            cache_hit=True
        )
        stats.add_record(record2)

        assert stats.total_calls == 2
        assert stats.cache_hits == 1
        assert stats.cache_hit_rate == 50.0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        stats = APIUsageStats()
        d = stats.to_dict()
        assert "total_calls" in d
        assert "cache_hit_rate_percent" in d
        assert "total_estimated_cost_usd" in d


# ============================================================================
# Test VisionElementFinder initialization
# ============================================================================

class TestVisionElementFinderInit:
    """Tests for VisionElementFinder initialization."""

    @pytest.fixture
    def mock_anthropic(self):
        """Create a patched anthropic module."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            # Re-import to get the patched version
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)
            yield vision_finder

    def test_missing_api_key_raises(self, mock_anthropic):
        """Test that missing API key raises ValueError."""
        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(ValueError, match="API key required"):
                mock_anthropic.VisionElementFinder()

    def test_init_with_api_key_param(self, mock_anthropic):
        """Test initialization with API key parameter."""
        finder = mock_anthropic.VisionElementFinder(api_key="test-key-123")
        assert finder._api_key == "test-key-123"

    def test_init_with_env_var(self, mock_anthropic):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key-456"}):
            finder = mock_anthropic.VisionElementFinder()
            assert finder._api_key == "env-key-456"

    def test_init_custom_model(self, mock_anthropic):
        """Test initialization with custom model."""
        finder = mock_anthropic.VisionElementFinder(
            api_key="test-key",
            model="claude-opus-4-20250514"
        )
        assert finder._model == "claude-opus-4-20250514"

    def test_init_custom_confidence(self, mock_anthropic):
        """Test initialization with custom confidence threshold."""
        finder = mock_anthropic.VisionElementFinder(
            api_key="test-key",
            min_confidence=0.9
        )
        assert finder._min_confidence == 0.9


# ============================================================================
# Test VisionElementFinder caching
# ============================================================================

class TestVisionElementFinderCaching:
    """Tests for VisionElementFinder caching functionality."""

    @pytest.fixture
    def finder_with_mock(self):
        """Create a VisionElementFinder with mocked client."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            finder = vision_finder.VisionElementFinder(api_key="test-key")

            # Mock the API client
            mock_response = MockResponse(json.dumps({
                "found": True,
                "x": 100,
                "y": 200,
                "confidence": 0.95,
                "description": "Build button",
                "element_type": "button"
            }))
            finder._client.messages.create = MagicMock(return_value=mock_response)

            yield finder

    def test_cache_key_generation(self, finder_with_mock):
        """Test cache key generation is consistent."""
        key1 = finder_with_mock._get_cache_key(SAMPLE_PNG, "Build button")
        key2 = finder_with_mock._get_cache_key(SAMPLE_PNG, "Build button")
        assert key1 == key2

        # Different image should give different key
        key3 = finder_with_mock._get_cache_key(SAMPLE_PNG_2, "Build button")
        assert key1 != key3

        # Different query should give different key
        key4 = finder_with_mock._get_cache_key(SAMPLE_PNG, "File menu")
        assert key1 != key4

    def test_cache_hit(self, finder_with_mock):
        """Test that cached results are returned."""
        # First call should hit API
        result1 = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert result1 is not None
        assert finder_with_mock._client.messages.create.call_count == 1

        # Second call should use cache
        result2 = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert result2 is not None
        assert finder_with_mock._client.messages.create.call_count == 1  # Still 1

        # Results should be identical
        assert result1.x == result2.x
        assert result1.y == result2.y

    def test_cache_miss_different_query(self, finder_with_mock):
        """Test cache miss on different query."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        finder_with_mock.find_element(SAMPLE_PNG, "File menu")
        assert finder_with_mock._client.messages.create.call_count == 2

    def test_cache_disabled(self, finder_with_mock):
        """Test caching can be disabled."""
        finder_with_mock._enable_caching = False

        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert finder_with_mock._client.messages.create.call_count == 2

    def test_cache_clear(self, finder_with_mock):
        """Test cache clearing."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert len(finder_with_mock._cache) == 1

        finder_with_mock.clear_cache()
        assert len(finder_with_mock._cache) == 0

        # Next call should hit API again
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert finder_with_mock._client.messages.create.call_count == 2

    def test_cache_ttl_expiry(self, finder_with_mock):
        """Test cache entry expiration."""
        # Set a very short TTL
        finder_with_mock._cache_ttl = 0.1  # 100ms

        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert finder_with_mock._client.messages.create.call_count == 1

        # Wait for TTL to expire
        time.sleep(0.2)

        # Should call API again
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert finder_with_mock._client.messages.create.call_count == 2


# ============================================================================
# Test VisionElementFinder API response parsing
# ============================================================================

class TestVisionElementFinderParsing:
    """Tests for API response parsing."""

    @pytest.fixture
    def finder_with_mock(self):
        """Create a VisionElementFinder with mocked client."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            finder = vision_finder.VisionElementFinder(api_key="test-key")
            yield finder

    def test_parse_found_element(self, finder_with_mock):
        """Test parsing a successful find response."""
        mock_response = MockResponse(json.dumps({
            "found": True,
            "x": 150,
            "y": 250,
            "confidence": 0.92,
            "description": "The Build button in the toolbar",
            "element_type": "button",
            "bounding_box": [140, 240, 160, 260]
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Build button")

        assert result is not None
        assert result.x == 150
        assert result.y == 250
        assert result.confidence == 0.92
        assert result.element_type == "button"
        assert result.bounding_box == (140, 240, 160, 260)

    def test_parse_not_found_element(self, finder_with_mock):
        """Test parsing when element is not found."""
        mock_response = MockResponse(json.dumps({
            "found": False,
            "x": 0,
            "y": 0,
            "confidence": 0.0,
            "description": "Could not find the specified element"
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Non-existent button")
        assert result is None

    def test_parse_low_confidence(self, finder_with_mock):
        """Test parsing when confidence is below threshold."""
        mock_response = MockResponse(json.dumps({
            "found": True,
            "x": 100,
            "y": 200,
            "confidence": 0.5,  # Below default 0.7 threshold
            "description": "Might be a Build button"
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert result is None

    def test_parse_markdown_code_block(self, finder_with_mock):
        """Test parsing JSON wrapped in markdown code block."""
        mock_response = MockResponse("""```json
{
    "found": true,
    "x": 100,
    "y": 200,
    "confidence": 0.95,
    "description": "Build button"
}
```""")
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert result is not None
        assert result.x == 100
        assert result.y == 200

    def test_parse_invalid_json(self, finder_with_mock):
        """Test handling of invalid JSON response."""
        mock_response = MockResponse("This is not valid JSON")
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        assert result is None

    def test_parse_missing_fields(self, finder_with_mock):
        """Test handling of response missing required fields."""
        mock_response = MockResponse(json.dumps({
            "found": True
            # Missing x, y, confidence
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        result = finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        # Should still work with defaults (0, 0) but confidence 0 won't pass threshold
        assert result is None


# ============================================================================
# Test VisionElementFinder usage tracking
# ============================================================================

class TestVisionElementFinderUsageTracking:
    """Tests for API usage tracking."""

    @pytest.fixture
    def finder_with_mock(self):
        """Create a VisionElementFinder with mocked client."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            finder = vision_finder.VisionElementFinder(api_key="test-key")

            mock_response = MockResponse(
                json.dumps({
                    "found": True,
                    "x": 100,
                    "y": 200,
                    "confidence": 0.95,
                    "description": "Build button"
                }),
                input_tokens=1500,
                output_tokens=200
            )
            finder._client.messages.create = MagicMock(return_value=mock_response)

            yield finder

    def test_tracks_api_calls(self, finder_with_mock):
        """Test that API calls are tracked."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")

        stats = finder_with_mock.get_usage_stats()
        assert stats.total_calls == 1
        assert stats.total_input_tokens == 1500
        assert stats.total_output_tokens == 200

    def test_tracks_cache_hits(self, finder_with_mock):
        """Test that cache hits are tracked."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")  # Cache hit

        stats = finder_with_mock.get_usage_stats()
        assert stats.total_calls == 2
        assert stats.cache_hits == 1
        assert stats.cache_hit_rate == 50.0

    def test_reset_usage_stats(self, finder_with_mock):
        """Test resetting usage statistics."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")
        finder_with_mock.reset_usage_stats()

        stats = finder_with_mock.get_usage_stats()
        assert stats.total_calls == 0
        assert stats.total_input_tokens == 0

    def test_cost_estimation(self, finder_with_mock):
        """Test cost estimation in usage stats."""
        finder_with_mock.find_element(SAMPLE_PNG, "Build button")

        stats = finder_with_mock.get_usage_stats()
        # 1500 input tokens * $3/M + 200 output tokens * $15/M
        expected_cost = (1500 / 1_000_000 * 3.0) + (200 / 1_000_000 * 15.0)
        assert stats.total_estimated_cost_usd == pytest.approx(expected_cost, rel=0.01)


# ============================================================================
# Test VisionElementFinder find_all_elements
# ============================================================================

class TestVisionElementFinderFindAll:
    """Tests for finding multiple elements."""

    @pytest.fixture
    def finder_with_mock(self):
        """Create a VisionElementFinder with mocked client."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            finder = vision_finder.VisionElementFinder(api_key="test-key")
            yield finder

    def test_find_multiple_elements(self, finder_with_mock):
        """Test finding multiple matching elements."""
        mock_response = MockResponse(json.dumps({
            "count": 3,
            "elements": [
                {"x": 100, "y": 200, "confidence": 0.95, "description": "Button 1", "element_type": "button"},
                {"x": 300, "y": 200, "confidence": 0.85, "description": "Button 2", "element_type": "button"},
                {"x": 500, "y": 200, "confidence": 0.75, "description": "Button 3", "element_type": "button"},
            ]
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        results = finder_with_mock.find_all_elements(SAMPLE_PNG, "buttons")

        assert len(results) == 3
        assert results[0].x == 100
        assert results[1].x == 300
        assert results[2].x == 500

    def test_find_all_filters_low_confidence(self, finder_with_mock):
        """Test that low confidence results are filtered."""
        mock_response = MockResponse(json.dumps({
            "count": 3,
            "elements": [
                {"x": 100, "y": 200, "confidence": 0.95, "description": "Button 1"},
                {"x": 300, "y": 200, "confidence": 0.5, "description": "Button 2"},  # Below threshold
                {"x": 500, "y": 200, "confidence": 0.3, "description": "Button 3"},  # Below threshold
            ]
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        results = finder_with_mock.find_all_elements(SAMPLE_PNG, "buttons")

        assert len(results) == 1
        assert results[0].x == 100

    def test_find_all_empty_result(self, finder_with_mock):
        """Test finding no elements."""
        mock_response = MockResponse(json.dumps({
            "count": 0,
            "elements": []
        }))
        finder_with_mock._client.messages.create = MagicMock(return_value=mock_response)

        results = finder_with_mock.find_all_elements(SAMPLE_PNG, "non-existent")

        assert len(results) == 0


# ============================================================================
# Test convenience functions
# ============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_find_element_convenience(self):
        """Test the find_element convenience function."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                with patch.object(
                    vision_finder.VisionElementFinder,
                    'find_element',
                    return_value=ElementLocation(x=100, y=200, confidence=0.95, description="test")
                ):
                    result = vision_finder.find_element(SAMPLE_PNG, "test element")
                    # The mock should be called
                    assert result is not None

    def test_find_element_with_retry_success(self):
        """Test retry function succeeds on first try."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                mock_finder = MagicMock()
                mock_finder.find_element.return_value = ElementLocation(
                    x=100, y=200, confidence=0.95, description="test"
                )

                with patch.object(
                    vision_finder,
                    'VisionElementFinder',
                    return_value=mock_finder
                ):
                    result = vision_finder.find_element_with_retry(SAMPLE_PNG, "test", max_retries=3)
                    assert result is not None
                    assert mock_finder.find_element.call_count == 1


# ============================================================================
# Test error handling
# ============================================================================

class TestVisionElementFinderErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def finder_with_mock(self):
        """Create a VisionElementFinder with mocked client."""
        with patch.dict('sys.modules', {'anthropic': MagicMock()}):
            import importlib
            from agents.computer_use import vision_finder
            importlib.reload(vision_finder)

            finder = vision_finder.VisionElementFinder(api_key="test-key")
            yield finder, vision_finder

    def test_handles_api_error(self, finder_with_mock):
        """Test handling of API errors."""
        finder, vision_finder_module = finder_with_mock

        # Create a custom APIError class for testing
        class MockAPIError(Exception):
            """Mock API error for testing."""
            pass

        # Make the mock module's APIError class and have it raise the error
        vision_finder_module.anthropic.APIError = MockAPIError
        finder._client.messages.create.side_effect = MockAPIError("Test error")

        result = finder.find_element(SAMPLE_PNG, "Build button")
        assert result is None

    def test_set_min_confidence_validation(self, finder_with_mock):
        """Test validation of confidence threshold."""
        finder, _ = finder_with_mock

        with pytest.raises(ValueError):
            finder.set_min_confidence(-0.1)

        with pytest.raises(ValueError):
            finder.set_min_confidence(1.5)

        # Valid values should work
        finder.set_min_confidence(0.0)
        finder.set_min_confidence(1.0)
        finder.set_min_confidence(0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
