#!/usr/bin/env python3
"""
Unit tests for Gemini Provider

Tests cover:
- Provider initialization and configuration
- Text completion
- Vision completion (images and video frames)
- Google-specific safety settings and filters
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

from lib.providers.gemini_provider import GeminiProvider
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


class TestGeminiProviderInit(unittest.TestCase):
    """Test provider initialization"""

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration"""
        config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            base_url='https://generativelanguage.googleapis.com/v1beta',
            default_model='gemini-2.0-flash',
            input_cost_per_1k=0.075,
            output_cost_per_1k=0.30
        )
        provider = GeminiProvider(config)
        self.assertEqual(provider.config.api_key, 'test-key')
        self.assertEqual(provider.config.base_url, 'https://generativelanguage.googleapis.com/v1beta')

    def test_init_without_api_key(self):
        """Test initialization fails without API key"""
        config = ProviderConfig(
            name='gemini',
            api_key='disabled',
            enabled=False,
            default_model='gemini-2.0-flash'
        )
        with self.assertRaises(AuthenticationError):
            GeminiProvider(config)

    def test_init_sets_default_base_url(self):
        """Test that default base URL is set if not provided"""
        config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash'
        )
        provider = GeminiProvider(config)
        self.assertEqual(provider.config.base_url, 'https://generativelanguage.googleapis.com/v1beta')


class TestGeminiProviderMessageConversion(unittest.TestCase):
    """Test message format conversion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash'
        )
        self.provider = GeminiProvider(self.config)

    def test_convert_user_message(self):
        """Test converting user messages"""
        messages = [Message(role=MessageRole.USER, content='Hello')]
        result = self.provider._convert_messages_to_provider_format(messages)

        self.assertIn('contents', result)
        self.assertEqual(len(result['contents']), 1)
        self.assertEqual(result['contents'][0]['role'], 'user')
        self.assertEqual(result['contents'][0]['parts'][0]['text'], 'Hello')

    def test_convert_system_message(self):
        """Test converting system messages"""
        messages = [
            Message(role=MessageRole.SYSTEM, content='You are a helpful assistant'),
            Message(role=MessageRole.USER, content='Hello')
        ]
        result = self.provider._convert_messages_to_provider_format(messages)

        self.assertEqual(result['system_instruction'], 'You are a helpful assistant')
        self.assertEqual(len(result['contents']), 1)  # System message not in contents

    def test_convert_conversation(self):
        """Test converting a full conversation"""
        messages = [
            Message(role=MessageRole.SYSTEM, content='You are helpful'),
            Message(role=MessageRole.USER, content='Hello'),
            Message(role=MessageRole.ASSISTANT, content='Hi there!'),
            Message(role=MessageRole.USER, content='How are you?')
        ]
        result = self.provider._convert_messages_to_provider_format(messages)

        self.assertEqual(result['system_instruction'], 'You are helpful')
        self.assertEqual(len(result['contents']), 3)
        self.assertEqual(result['contents'][0]['role'], 'user')
        self.assertEqual(result['contents'][1]['role'], 'model')  # assistant -> model
        self.assertEqual(result['contents'][2]['role'], 'user')


class TestGeminiProviderComplete(unittest.TestCase):
    """Test text completion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            base_url='https://generativelanguage.googleapis.com/v1beta',
            default_model='gemini-2.0-flash',
            input_cost_per_1k=0.075,
            output_cost_per_1k=0.30
        )
        self.provider = GeminiProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_complete_success(self, mock_urlopen):
        """Test successful text completion"""
        # Mock API response
        mock_response = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Hello! How can I help you?'}]
                },
                'finishReason': 'STOP'
            }],
            'usageMetadata': {
                'promptTokenCount': 10,
                'candidatesTokenCount': 15,
                'totalTokenCount': 25
            }
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        # Make request
        messages = [Message(role=MessageRole.USER, content='Hello')]
        response = self.provider.complete(messages)

        # Assertions
        self.assertEqual(response.content, 'Hello! How can I help you?')
        self.assertEqual(response.model, 'gemini-2.0-flash')
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 15)
        self.assertEqual(response.provider, 'gemini')
        self.assertEqual(response.finish_reason, 'STOP')
        self.assertGreater(response.cost, 0)

    @patch('urllib.request.urlopen')
    def test_complete_with_custom_model(self, mock_urlopen):
        """Test completion with custom model"""
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'Response'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 5, 'totalTokenCount': 10}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Test')]
        response = self.provider.complete(messages, model='gemini-2.0-pro')

        self.assertEqual(response.model, 'gemini-2.0-pro')

    def test_complete_with_unsupported_model(self):
        """Test completion with unsupported model"""
        messages = [Message(role=MessageRole.USER, content='Test')]
        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages, model='unsupported-model')

    @patch('urllib.request.urlopen')
    def test_complete_with_temperature_and_max_tokens(self, mock_urlopen):
        """Test completion with custom temperature and max_tokens"""
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'Response'}]}, 'finishReason': 'MAX_TOKENS'}],
            'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 100, 'totalTokenCount': 105}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Test')]
        response = self.provider.complete(messages, temperature=0.9, max_tokens=100)

        self.assertEqual(response.finish_reason, 'MAX_TOKENS')
        self.assertEqual(response.usage.output_tokens, 100)

    @patch('urllib.request.urlopen')
    def test_complete_blocked_by_safety_filter(self, mock_urlopen):
        """Test handling of safety filter blocks"""
        mock_response = {
            'candidates': [{
                'content': {'parts': []},
                'finishReason': 'SAFETY',
                'safetyRatings': [
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'HIGH'}
                ]
            }],
            'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 0, 'totalTokenCount': 10}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Harmful content')]

        with self.assertRaises(InvalidRequestError) as context:
            self.provider.complete(messages)

        self.assertIn('safety filter', str(context.exception).lower())

    @patch('urllib.request.urlopen')
    def test_complete_with_grounding(self, mock_urlopen):
        """Test completion with Google Search grounding"""
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'Grounded response'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 15, 'candidatesTokenCount': 20, 'totalTokenCount': 35}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='What is the weather?')]
        response = self.provider.complete(messages, enable_grounding=True)

        self.assertEqual(response.content, 'Grounded response')


class TestGeminiProviderVision(unittest.TestCase):
    """Test vision completion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash',
            input_cost_per_1k=0.075,
            output_cost_per_1k=0.30
        )
        self.provider = GeminiProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_complete_with_vision_base64(self, mock_urlopen):
        """Test vision completion with base64 image"""
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'I see a cat'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 150, 'candidatesTokenCount': 20, 'totalTokenCount': 170}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='What is in this image?')]
        images = [ImageInput(base64='fake-base64-data', mime_type='image/jpeg')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'I see a cat')
        self.assertEqual(response.model, 'gemini-2.0-flash')

    @patch('urllib.request.urlopen')
    @patch('builtins.open', create=True)
    def test_complete_with_vision_file(self, mock_open, mock_urlopen):
        """Test vision completion with file path"""
        # Mock file read
        mock_file = MagicMock()
        mock_file.read.return_value = b'fake-image-data'
        mock_open.return_value.__enter__.return_value = mock_file

        # Mock API response
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'This is a dog'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 200, 'candidatesTokenCount': 25, 'totalTokenCount': 225}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        messages = [Message(role=MessageRole.USER, content='Describe the image')]
        images = [ImageInput(file_path='/path/to/image.jpg', mime_type='image/jpeg')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'This is a dog')
        mock_open.assert_called_once_with('/path/to/image.jpg', 'rb')

    def test_vision_with_non_vision_model(self):
        """Test that non-vision models raise error"""
        # Currently all Gemini 2.0 models support vision, but test the check
        messages = [Message(role=MessageRole.USER, content='Test')]
        images = [ImageInput(base64='fake-data')]

        # Would need a non-vision model to test this properly
        # For now, just test with unsupported model
        with self.assertRaises(InvalidRequestError):
            self.provider.complete_with_vision(messages, images, model='unsupported-model')

    @patch('urllib.request.urlopen')
    def test_complete_with_vision_url(self, mock_urlopen):
        """Test vision completion with URL image"""
        # Mock URL fetch for image
        image_response = MagicMock()
        image_response.read.return_value = b'fake-image-data'

        # Mock API response
        api_response = {
            'candidates': [{'content': {'parts': [{'text': 'Image from URL'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 180, 'candidatesTokenCount': 15, 'totalTokenCount': 195}
        }

        # Configure mock to handle both URL fetch and API call
        def urlopen_side_effect(request, **kwargs):
            if isinstance(request, str):  # Image URL
                mock = MagicMock()
                mock.__enter__.return_value = image_response
                return mock
            else:  # API call
                mock = MagicMock()
                mock.__enter__.return_value.read.return_value = json.dumps(api_response).encode()
                return mock

        mock_urlopen.side_effect = urlopen_side_effect

        messages = [Message(role=MessageRole.USER, content='What do you see?')]
        images = [ImageInput(url='https://example.com/image.jpg')]

        response = self.provider.complete_with_vision(messages, images)

        self.assertEqual(response.content, 'Image from URL')


class TestGeminiProviderErrorHandling(unittest.TestCase):
    """Test error handling"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash'
        )
        self.provider = GeminiProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_authentication_error_401(self, mock_urlopen):
        """Test 401 authentication error"""
        error = urllib.error.HTTPError(
            'url', 401, 'Unauthorized', {}, None
        )
        error.read = lambda: json.dumps({'error': {'message': 'Invalid API key'}}).encode()
        mock_urlopen.side_effect = error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(AuthenticationError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_rate_limit_error_429(self, mock_urlopen):
        """Test 429 rate limit error"""
        error = urllib.error.HTTPError(
            'url', 429, 'Too Many Requests', {}, None
        )
        error.read = lambda: json.dumps({'error': {'message': 'Rate limit exceeded'}}).encode()
        mock_urlopen.side_effect = error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(RateLimitError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_invalid_request_error_400(self, mock_urlopen):
        """Test 400 invalid request error"""
        error = urllib.error.HTTPError(
            'url', 400, 'Bad Request', {}, None
        )
        error.read = lambda: json.dumps({'error': {'message': 'Invalid parameters'}}).encode()
        mock_urlopen.side_effect = error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_generic_http_error_500(self, mock_urlopen):
        """Test 500 server error"""
        error = urllib.error.HTTPError(
            'url', 500, 'Internal Server Error', {}, None
        )
        error.read = lambda: json.dumps({'error': {'message': 'Server error'}}).encode()
        mock_urlopen.side_effect = error

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(InvalidRequestError):
            self.provider.complete(messages)

    @patch('urllib.request.urlopen')
    def test_timeout_error(self, mock_urlopen):
        """Test timeout error"""
        mock_urlopen.side_effect = urllib.error.URLError('Timeout')

        messages = [Message(role=MessageRole.USER, content='Test')]

        with self.assertRaises(LLMTimeoutError):
            self.provider.complete(messages)


class TestGeminiProviderTestConnection(unittest.TestCase):
    """Test connection testing"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash'
        )
        self.provider = GeminiProvider(self.config)

    @patch('urllib.request.urlopen')
    def test_connection_success(self, mock_urlopen):
        """Test successful connection"""
        mock_response = {
            'candidates': [{'content': {'parts': [{'text': 'Hi'}]}, 'finishReason': 'STOP'}],
            'usageMetadata': {'promptTokenCount': 2, 'candidatesTokenCount': 1, 'totalTokenCount': 3}
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        success, message = self.provider.test_connection()

        self.assertTrue(success)
        self.assertIn('gemini-2.0-flash', message.lower())

    @patch('urllib.request.urlopen')
    def test_connection_failure(self, mock_urlopen):
        """Test connection failure"""
        error = urllib.error.HTTPError(
            'url', 401, 'Unauthorized', {}, None
        )
        error.read = lambda: json.dumps({'error': {'message': 'Invalid API key'}}).encode()
        mock_urlopen.side_effect = error

        success, message = self.provider.test_connection()

        self.assertFalse(success)
        self.assertIn('failed', message.lower())


class TestGeminiProviderImageConversion(unittest.TestCase):
    """Test image format conversion"""

    def setUp(self):
        """Set up test provider"""
        self.config = ProviderConfig(
            name='gemini',
            api_key='test-key',
            default_model='gemini-2.0-flash'
        )
        self.provider = GeminiProvider(self.config)

    def test_convert_base64_image(self):
        """Test converting base64 image"""
        images = [ImageInput(base64='base64data', mime_type='image/png')]
        result = self.provider._convert_images_to_provider_format(images)

        self.assertEqual(len(result), 1)
        self.assertIn('inline_data', result[0])
        self.assertEqual(result[0]['inline_data']['mime_type'], 'image/png')
        self.assertEqual(result[0]['inline_data']['data'], 'base64data')

    @patch('builtins.open', create=True)
    def test_convert_file_path_image(self, mock_open):
        """Test converting file path image"""
        mock_file = MagicMock()
        mock_file.read.return_value = b'fake-image-data'
        mock_open.return_value.__enter__.return_value = mock_file

        images = [ImageInput(file_path='/path/to/image.jpg')]
        result = self.provider._convert_images_to_provider_format(images)

        self.assertEqual(len(result), 1)
        self.assertIn('inline_data', result[0])
        mock_open.assert_called_once_with('/path/to/image.jpg', 'rb')


if __name__ == '__main__':
    unittest.main()
