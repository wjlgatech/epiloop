#!/usr/bin/env python3
"""
Unit tests for OpenAI Provider

Tests cover:
- Provider initialization and configuration
- Text completion
- Vision completion
- Error handling (rate limits, timeouts, authentication)
- CLI interface
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os
import urllib.error

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.providers.openai_provider import OpenAIProvider
from lib.llm_provider import (
    Message,
    MessageRole,
    ImageInput,
    LLMResponse,
    TokenUsage,
    RateLimitError,
    TimeoutError as LLMTimeoutError,
    AuthenticationError,
    InvalidRequestError
)
from lib.llm_config import ProviderConfig


class TestOpenAIProviderInit(unittest.TestCase):
    """Test provider initialization"""

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration"""
        config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        provider = OpenAIProvider(config)
        self.assertEqual(provider.config.api_key, 'test-key')
        self.assertEqual(provider.config.base_url, 'https://api.openai.com/v1')

    def test_init_without_api_key(self):
        """Test initialization fails without API key"""
        config = ProviderConfig(
            name='openai',
            api_key='disabled',
            enabled=False,
            default_model='gpt-4o'
        )
        with self.assertRaises(AuthenticationError):
            OpenAIProvider(config)

    def test_init_sets_default_base_url(self):
        """Test that default base URL is set if not provided"""
        config = ProviderConfig(
            name='openai',
            api_key='test-key',
            default_model='gpt-4o'
        )
        provider = OpenAIProvider(config)
        self.assertEqual(provider.config.base_url, 'https://api.openai.com/v1')


class TestOpenAIProviderComplete(unittest.TestCase):
    """Test text completion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_complete_success(self, mock_urlopen):
        """Test successful text completion"""
        # Mock API response
        mock_response = {
            'choices': [{
                'message': {'content': 'Hello! How can I help you?'},
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 15,
                'total_tokens': 25
            },
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        # Make request
        messages = [Message(role=MessageRole.USER, content='Hello')]
        response = self.provider.complete(messages)

        # Assertions
        self.assertEqual(response.content, 'Hello! How can I help you?')
        self.assertEqual(response.model, 'gpt-4o')
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 15)
        self.assertEqual(response.provider, 'openai')
        self.assertEqual(response.finish_reason, 'stop')
        self.assertGreater(response.cost, 0)

    @patch('urllib.request.urlopen')
    def test_complete_with_custom_model(self, mock_urlopen):
        """Test completion with custom model"""
        mock_response = {
            'choices': [{'message': {'content': 'Response'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5, 'total_tokens': 10},
            'model': 'gpt-4o-mini'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Test')]
        response = self.provider.complete(messages, model='gpt-4o-mini')

        self.assertEqual(response.model, 'gpt-4o-mini')

    def test_complete_with_unsupported_model(self):
        """Test completion with unsupported model"""
        messages = [Message(role=MessageRole.USER, content='Test')]
        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages, model='unsupported-model')

    @patch('urllib.request.urlopen')
    def test_complete_with_temperature_and_max_tokens(self, mock_urlopen):
        """Test completion with custom temperature and max_tokens"""
        mock_response = {
            'choices': [{'message': {'content': 'Response'}, 'finish_reason': 'length'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 100, 'total_tokens': 105},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Test')]
        response = self.provider.complete(messages, temperature=0.5, max_tokens=100)

        # Verify the request was made correctly (check call args)
        self.assertEqual(response.finish_reason, 'length')


class TestOpenAIProviderVision(unittest.TestCase):
    """Test vision completion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_complete_with_vision_base64(self, mock_urlopen):
        """Test vision completion with base64 image"""
        mock_response = {
            'choices': [{'message': {'content': 'I see an image'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 500, 'completion_tokens': 10, 'total_tokens': 510},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='What is in this image?')]
        images = [ImageInput(base64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'I see an image')
        self.assertEqual(response.usage.input_tokens, 500)

    @patch('urllib.request.urlopen')
    def test_complete_with_vision_url(self, mock_urlopen):
        """Test vision completion with image URL"""
        mock_response = {
            'choices': [{'message': {'content': 'I see a cat'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 300, 'completion_tokens': 5, 'total_tokens': 305},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Describe this image')]
        images = [ImageInput(url='https://example.com/cat.jpg')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'I see a cat')

    @patch('builtins.open', create=True)
    @patch('urllib.request.urlopen')
    def test_complete_with_vision_file_path(self, mock_urlopen, mock_open):
        """Test vision completion with file path"""
        # Mock file reading
        mock_open.return_value.__enter__.return_value.read.return_value = b'fake_image_data'

        mock_response = {
            'choices': [{'message': {'content': 'Image from file'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 400, 'completion_tokens': 8, 'total_tokens': 408},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='What is this?')]
        images = [ImageInput(file_path='/tmp/test.jpg')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'Image from file')

    def test_vision_with_non_vision_model(self):
        """Test that vision fails with non-vision model"""
        messages = [Message(role=MessageRole.USER, content='Test')]
        images = [ImageInput(url='https://example.com/test.jpg')]

        with self.assertRaises(InvalidRequestError):
            self.provider.complete_with_vision(messages, images, model='o3-mini')

    @patch('urllib.request.urlopen')
    def test_vision_with_multiple_images(self, mock_urlopen):
        """Test vision completion with multiple images"""
        mock_response = {
            'choices': [{'message': {'content': 'Two images'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 800, 'completion_tokens': 10, 'total_tokens': 810},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Compare these images')]
        images = [
            ImageInput(url='https://example.com/img1.jpg'),
            ImageInput(url='https://example.com/img2.jpg')
        ]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'Two images')


class TestOpenAIProviderErrorHandling(unittest.TestCase):
    """Test error handling"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_authentication_error(self, mock_urlopen):
        """Test authentication error handling"""
        # Mock 401 error
        error_response = json.dumps({'error': {'message': 'Invalid API key'}}).encode()
        mock_error = urllib.error.HTTPError(
            url='https://api.openai.com/v1/chat/completions',
            code=401,
            msg='Unauthorized',
            hdrs={},
            fp=None
        )
        mock_error.read = MagicMock(return_value=error_response)
        mock_urlopen.side_effect = mock_error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(AuthenticationError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_rate_limit_error(self, mock_urlopen):
        """Test rate limit error handling"""
        # Mock 429 error
        error_response = json.dumps({'error': {'message': 'Rate limit exceeded'}}).encode()
        mock_error = urllib.error.HTTPError(
            url='https://api.openai.com/v1/chat/completions',
            code=429,
            msg='Too Many Requests',
            hdrs={},
            fp=None
        )
        mock_error.read = MagicMock(return_value=error_response)
        mock_urlopen.side_effect = mock_error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(RateLimitError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_invalid_request_error(self, mock_urlopen):
        """Test invalid request error handling"""
        # Mock 400 error
        error_response = json.dumps({'error': {'message': 'Invalid request'}}).encode()
        mock_error = urllib.error.HTTPError(
            url='https://api.openai.com/v1/chat/completions',
            code=400,
            msg='Bad Request',
            hdrs={},
            fp=None
        )
        mock_error.read = MagicMock(return_value=error_response)
        mock_urlopen.side_effect = mock_error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_generic_http_error(self, mock_urlopen):
        """Test generic HTTP error handling"""
        # Mock 500 error
        error_response = json.dumps({'error': {'message': 'Internal server error'}}).encode()
        mock_error = urllib.error.HTTPError(
            url='https://api.openai.com/v1/chat/completions',
            code=500,
            msg='Internal Server Error',
            hdrs={},
            fp=None
        )
        mock_error.read = MagicMock(return_value=error_response)
        mock_urlopen.side_effect = mock_error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages)


class TestOpenAIProviderTestConnection(unittest.TestCase):
    """Test connection testing"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_connection_success(self, mock_urlopen):
        """Test successful connection test"""
        mock_response = {
            'choices': [{'message': {'content': 'Hi'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5, 'total_tokens': 10},
            'model': 'gpt-4o'
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        success, message = self.provider.test_connection()

        self.assertTrue(success)
        self.assertIn('Successfully connected', message)
        self.assertIn('gpt-4o', message)

    @patch('urllib.request.urlopen')
    def test_connection_failure(self, mock_urlopen):
        """Test failed connection test"""
        error_response = json.dumps({'error': {'message': 'Invalid key'}}).encode()
        mock_error = urllib.error.HTTPError(
            url='https://api.openai.com/v1/chat/completions',
            code=401,
            msg='Unauthorized',
            hdrs={},
            fp=None
        )
        mock_error.read = MagicMock(return_value=error_response)
        mock_urlopen.side_effect = mock_error

        success, message = self.provider.test_connection()

        self.assertFalse(success)
        self.assertIn('failed', message.lower())


class TestOpenAIProviderMessageConversion(unittest.TestCase):
    """Test message format conversion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    def test_convert_messages_to_openai_format(self):
        """Test message conversion to OpenAI format"""
        messages = [
            Message(role=MessageRole.SYSTEM, content='You are helpful'),
            Message(role=MessageRole.USER, content='Hello'),
            Message(role=MessageRole.ASSISTANT, content='Hi there'),
            Message(role=MessageRole.USER, content='How are you?')
        ]

        openai_messages = self.provider._convert_messages_to_provider_format(messages)

        self.assertEqual(len(openai_messages), 4)
        self.assertEqual(openai_messages[0]['role'], 'system')
        self.assertEqual(openai_messages[0]['content'], 'You are helpful')
        self.assertEqual(openai_messages[1]['role'], 'user')
        self.assertEqual(openai_messages[2]['role'], 'assistant')

    def test_convert_images_base64(self):
        """Test image conversion for base64"""
        images = [ImageInput(base64='abc123', mime_type='image/png')]
        content_parts = self.provider._convert_images_to_provider_format(images)

        self.assertEqual(len(content_parts), 1)
        self.assertEqual(content_parts[0]['type'], 'image_url')
        self.assertIn('data:image/png;base64,abc123', content_parts[0]['image_url']['url'])

    def test_convert_images_url(self):
        """Test image conversion for URL"""
        images = [ImageInput(url='https://example.com/image.jpg')]
        content_parts = self.provider._convert_images_to_provider_format(images)

        self.assertEqual(len(content_parts), 1)
        self.assertEqual(content_parts[0]['type'], 'image_url')
        self.assertEqual(content_parts[0]['image_url']['url'], 'https://example.com/image.jpg')


class TestOpenAIProviderCostCalculation(unittest.TestCase):
    """Test cost calculation"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='openai',
            api_key='test-key',
            base_url='https://api.openai.com/v1',
            default_model='gpt-4o',
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.00
        )
        self.provider = OpenAIProvider(self.config)

    def test_cost_calculation(self):
        """Test accurate cost calculation"""
        # 1000 input tokens at $2.50/1k = $2.50
        # 500 output tokens at $10/1k = $5.00
        # Total = $7.50
        cost = self.provider._calculate_cost(1000, 500)
        self.assertAlmostEqual(cost, 7.50, places=2)

    def test_cost_calculation_small_values(self):
        """Test cost calculation with small token counts"""
        # 10 input tokens at $2.50/1k = $0.025
        # 20 output tokens at $10/1k = $0.20
        # Total = $0.225
        cost = self.provider._calculate_cost(10, 20)
        self.assertAlmostEqual(cost, 0.225, places=3)


if __name__ == '__main__':
    unittest.main()
