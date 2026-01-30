#!/usr/bin/env python3
"""
Unit tests for LLM Provider Abstraction Layer

Tests the abstract provider interface, message formatting, retry logic,
timeout handling, and provider factory.
"""

import unittest
import sys
import os
from unittest.mock import patch
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.llm_provider import (
    LLMProvider,
    Message,
    MessageRole,
    ImageInput,
    TokenUsage,
    LLMResponse,
    ProviderFactory,
    RateLimitError,
    TimeoutError,
    AuthenticationError,
    InvalidRequestError
)
from lib.llm_config import ProviderConfig


class MockProvider(LLMProvider):
    """Mock provider for testing"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.call_count = 0
        self.should_fail = False
        self.failure_type: Optional[str] = None
        self.fail_times = 0

    def complete(self, messages, model=None, temperature=0.7, max_tokens=None, **kwargs):
        _ = (messages, temperature, max_tokens, kwargs)  # Mark as used
        self.call_count += 1

        # Simulate failures for retry testing
        if self.should_fail and self.call_count <= self.fail_times:
            if self.failure_type == 'rate_limit':
                raise RateLimitError("Rate limit exceeded")
            elif self.failure_type == 'timeout':
                raise TimeoutError("Request timeout")
            elif self.failure_type == 'auth':
                raise AuthenticationError("Invalid API key")
            elif self.failure_type == 'invalid':
                raise InvalidRequestError("Invalid parameters")

        # Ensure model is always a string
        model_name = model if model else (self.config.default_model if self.config.default_model else "test-model")

        # Return mock response
        return LLMResponse(
            content="Mock response",
            model=model_name,
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=self._calculate_cost(10, 20),
            provider=self.provider_name,
            finish_reason="stop"
        )

    def complete_with_vision(self, messages, images, model=None, temperature=0.7, max_tokens=None, **kwargs):
        _ = (messages, images, temperature, max_tokens, kwargs)  # Mark as used
        self.call_count += 1

        # Ensure model is always a string
        model_name = model if model else (self.config.default_model if self.config.default_model else "test-model")

        return LLMResponse(
            content="Mock vision response",
            model=model_name,
            usage=TokenUsage(input_tokens=15, output_tokens=25, total_tokens=40),
            cost=self._calculate_cost(15, 25),
            provider=self.provider_name,
            finish_reason="stop"
        )

    def _convert_messages_to_provider_format(self, messages):
        return [msg.to_dict() for msg in messages]

    def _parse_provider_response(self, response, model):
        _ = model  # Mark as used
        return response


class TestMessage(unittest.TestCase):
    """Test Message dataclass"""

    def test_message_creation(self):
        """Test creating messages with different roles"""
        msg = Message(role=MessageRole.USER, content="Hello")
        self.assertEqual(msg.role, MessageRole.USER)
        self.assertEqual(msg.content, "Hello")

    def test_message_to_dict(self):
        """Test converting message to dictionary"""
        msg = Message(role=MessageRole.ASSISTANT, content="Hi there")
        result = msg.to_dict()
        self.assertEqual(result["role"], "assistant")
        self.assertEqual(result["content"], "Hi there")


class TestImageInput(unittest.TestCase):
    """Test ImageInput dataclass"""

    def test_base64_input(self):
        """Test creating image from base64"""
        img = ImageInput(base64="abc123")
        self.assertEqual(img.base64, "abc123")
        self.assertIsNone(img.url)
        self.assertIsNone(img.file_path)

    def test_url_input(self):
        """Test creating image from URL"""
        img = ImageInput(url="https://example.com/image.jpg")
        self.assertEqual(img.url, "https://example.com/image.jpg")
        self.assertIsNone(img.base64)
        self.assertIsNone(img.file_path)

    def test_file_path_input(self):
        """Test creating image from file path"""
        img = ImageInput(file_path="/path/to/image.jpg")
        self.assertEqual(img.file_path, "/path/to/image.jpg")
        self.assertIsNone(img.base64)
        self.assertIsNone(img.url)

    def test_multiple_inputs_raises_error(self):
        """Test that providing multiple inputs raises ValueError"""
        with self.assertRaises(ValueError):
            ImageInput(base64="abc", url="https://example.com/img.jpg")

    def test_no_input_raises_error(self):
        """Test that providing no input raises ValueError"""
        with self.assertRaises(ValueError):
            ImageInput()


class TestTokenUsage(unittest.TestCase):
    """Test TokenUsage dataclass"""

    def test_token_usage_creation(self):
        """Test creating token usage"""
        usage = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 200)
        self.assertEqual(usage.total_tokens, 300)

    def test_token_usage_to_dict(self):
        """Test converting to dictionary"""
        usage = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300)
        result = usage.to_dict()
        self.assertEqual(result["input_tokens"], 100)
        self.assertEqual(result["output_tokens"], 200)
        self.assertEqual(result["total_tokens"], 300)


class TestLLMResponse(unittest.TestCase):
    """Test LLMResponse dataclass"""

    def test_response_creation(self):
        """Test creating LLM response"""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        response = LLMResponse(
            content="Test response",
            model="test-model",
            usage=usage,
            cost=0.05,
            provider="test"
        )
        self.assertEqual(response.content, "Test response")
        self.assertEqual(response.model, "test-model")
        self.assertEqual(response.cost, 0.05)

    def test_response_to_dict(self):
        """Test converting response to dictionary"""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        response = LLMResponse(
            content="Test",
            model="test-model",
            usage=usage,
            cost=0.05,
            provider="test",
            finish_reason="stop"
        )
        result = response.to_dict()
        self.assertEqual(result["content"], "Test")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["cost"], 0.05)
        self.assertEqual(result["finish_reason"], "stop")


class TestLLMProvider(unittest.TestCase):
    """Test LLMProvider base class"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ProviderConfig(
            name="test",
            enabled=True,
            api_key="test-key",
            base_url="https://api.test.com",
            timeout=30,
            max_tokens=1000,
            default_model="test-model",
            input_cost_per_1k=1.0,
            output_cost_per_1k=2.0
        )
        self.provider = MockProvider(self.config)

    def test_provider_initialization(self):
        """Test provider initialization"""
        self.assertEqual(self.provider.config.name, "test")
        self.assertEqual(self.provider.provider_name, "test")

    def test_calculate_cost(self):
        """Test cost calculation"""
        cost = self.provider._calculate_cost(1000, 500)
        expected = (1000 / 1000) * 1.0 + (500 / 1000) * 2.0
        self.assertAlmostEqual(cost, expected)

    def test_complete_basic(self):
        """Test basic completion"""
        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = self.provider.complete(messages)
        self.assertEqual(response.content, "Mock response")
        self.assertEqual(self.provider.call_count, 1)

    def test_complete_with_vision(self):
        """Test completion with vision"""
        messages = [Message(role=MessageRole.USER, content="What's in this image?")]
        images = [ImageInput(url="https://example.com/image.jpg")]
        response = self.provider.complete_with_vision(messages, images)
        self.assertEqual(response.content, "Mock vision response")

    def test_test_connection(self):
        """Test connection testing"""
        success, message = self.provider.test_connection()
        self.assertTrue(success)
        self.assertIn("test-model", message)

    def test_retry_with_backoff_success_after_failure(self):
        """Test retry logic succeeds after initial failures"""
        self.provider.should_fail = True
        self.provider.failure_type = 'rate_limit'
        self.provider.fail_times = 2

        messages = [Message(role=MessageRole.USER, content="Test")]

        # Should succeed on third attempt
        response = self.provider._retry_with_backoff(
            lambda: self.provider.complete(messages),
            max_retries=3,
            initial_delay=0.01,
            backoff_factor=2.0
        )

        self.assertEqual(response.content, "Mock response")
        self.assertEqual(self.provider.call_count, 3)

    def test_retry_with_backoff_exhausts_retries(self):
        """Test retry logic exhausts all retries"""
        self.provider.should_fail = True
        self.provider.failure_type = 'rate_limit'
        self.provider.fail_times = 10  # More than max retries

        messages = [Message(role=MessageRole.USER, content="Test")]

        with self.assertRaises(RateLimitError):
            self.provider._retry_with_backoff(
                lambda: self.provider.complete(messages),
                max_retries=2,
                initial_delay=0.01
            )

    def test_retry_no_retry_on_auth_error(self):
        """Test that authentication errors are not retried"""
        self.provider.should_fail = True
        self.provider.failure_type = 'auth'
        self.provider.fail_times = 1

        messages = [Message(role=MessageRole.USER, content="Test")]

        with self.assertRaises(AuthenticationError):
            self.provider._retry_with_backoff(
                lambda: self.provider.complete(messages),
                max_retries=3
            )

        # Should only be called once (no retries)
        self.assertEqual(self.provider.call_count, 1)

    def test_retry_no_retry_on_invalid_request(self):
        """Test that invalid request errors are not retried"""
        self.provider.should_fail = True
        self.provider.failure_type = 'invalid'
        self.provider.fail_times = 1

        messages = [Message(role=MessageRole.USER, content="Test")]

        with self.assertRaises(InvalidRequestError):
            self.provider._retry_with_backoff(
                lambda: self.provider.complete(messages),
                max_retries=3
            )

        # Should only be called once (no retries)
        self.assertEqual(self.provider.call_count, 1)

    @patch('signal.signal')
    @patch('signal.alarm')
    def test_with_timeout_success(self, mock_alarm, _mock_signal):
        """Test timeout handling with successful execution"""
        result = self.provider._with_timeout(lambda: "success", timeout=10)
        self.assertEqual(result, "success")
        mock_alarm.assert_called()

    @patch('signal.signal')
    @patch('signal.alarm')
    def test_with_timeout_uses_config_default(self, mock_alarm, _mock_signal):
        """Test that timeout uses config default when not specified"""
        self.provider._with_timeout(lambda: "success")
        # Should use config timeout (30 seconds)
        calls = mock_alarm.call_args_list
        self.assertTrue(any(call[0][0] == 30 for call in calls if call[0]))


class TestProviderFactory(unittest.TestCase):
    """Test ProviderFactory"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ProviderConfig(
            name="mock",
            enabled=True,
            api_key="test-key",
            default_model="test-model",
            input_cost_per_1k=1.0,
            output_cost_per_1k=2.0
        )

    def test_register_provider(self):
        """Test registering a provider"""
        ProviderFactory.register("mock", MockProvider)
        self.assertIn("mock", ProviderFactory.list_registered())

    def test_register_invalid_provider_raises_error(self):
        """Test that registering non-LLMProvider class raises error"""
        class NotAProvider:
            pass

        with self.assertRaises(ValueError):
            ProviderFactory.register("invalid", NotAProvider)

    def test_create_provider(self):
        """Test creating a provider instance"""
        ProviderFactory.register("mock", MockProvider)
        provider = ProviderFactory.create(self.config)
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.config.name, "mock")

    def test_create_unregistered_provider_raises_error(self):
        """Test that creating unregistered provider raises error"""
        config = ProviderConfig(
            name="nonexistent",
            enabled=True,
            api_key="test-key",
            default_model="test-model",
            input_cost_per_1k=1.0,
            output_cost_per_1k=2.0
        )
        with self.assertRaises(ValueError):
            ProviderFactory.create(config)

    def test_list_registered_providers(self):
        """Test listing registered providers"""
        ProviderFactory.register("mock1", MockProvider)
        ProviderFactory.register("mock2", MockProvider)
        registered = ProviderFactory.list_registered()
        self.assertIn("mock1", registered)
        self.assertIn("mock2", registered)


class TestProviderErrors(unittest.TestCase):
    """Test provider error types"""

    def test_rate_limit_error(self):
        """Test RateLimitError"""
        with self.assertRaises(RateLimitError) as context:
            raise RateLimitError("Rate limit exceeded")
        self.assertIn("Rate limit", str(context.exception))

    def test_timeout_error(self):
        """Test TimeoutError"""
        with self.assertRaises(TimeoutError) as context:
            raise TimeoutError("Request timeout")
        self.assertIn("timeout", str(context.exception))

    def test_authentication_error(self):
        """Test AuthenticationError"""
        with self.assertRaises(AuthenticationError) as context:
            raise AuthenticationError("Invalid API key")
        self.assertIn("Invalid", str(context.exception))

    def test_invalid_request_error(self):
        """Test InvalidRequestError"""
        with self.assertRaises(InvalidRequestError) as context:
            raise InvalidRequestError("Invalid parameters")
        self.assertIn("Invalid", str(context.exception))


if __name__ == '__main__':
    unittest.main()
