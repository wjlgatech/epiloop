"""
Unit tests for DeepSeek Provider

Tests all functionality of the DeepSeek provider including:
- Basic configuration and initialization
- Text completion (deepseek-chat)
- Reasoning mode (deepseek-reasoner with Chain-of-Thought)
- Error handling (auth, rate limit, timeout, invalid requests)
- Cost calculation
- Retry logic
- CLI interface
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.providers.deepseek_provider import DeepSeekProvider
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


class TestDeepSeekProvider(unittest.TestCase):
    """Test suite for DeepSeek provider"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ProviderConfig(
            name='deepseek',
            api_key='test-api-key',
            base_url='https://api.deepseek.com',
            timeout=30,
            max_tokens=4096,
            default_model='deepseek-chat',
            available_models=['deepseek-chat', 'deepseek-reasoner'],
            input_cost_per_1k=0.28,
            output_cost_per_1k=0.42
        )

    def test_initialization_success(self):
        """Test successful provider initialization"""
        provider = DeepSeekProvider(self.config)
        self.assertEqual(provider.config.name, 'deepseek')
        self.assertEqual(provider.config.api_key, 'test-api-key')
        self.assertEqual(provider.config.base_url, 'https://api.deepseek.com')

    def test_initialization_no_api_key(self):
        """Test initialization fails without API key"""
        config = ProviderConfig(
            name='deepseek',
            api_key=None,
            enabled=False
        )
        with self.assertRaises(AuthenticationError):
            DeepSeekProvider(config)

    def test_initialization_disabled_api_key(self):
        """Test initialization fails with disabled API key"""
        config = ProviderConfig(
            name='deepseek',
            api_key='disabled',
            enabled=False
        )
        with self.assertRaises(AuthenticationError):
            DeepSeekProvider(config)

    def test_initialization_default_base_url(self):
        """Test default base URL is set if not provided"""
        config = ProviderConfig(
            name='deepseek',
            api_key='test-key',
            base_url=None
        )
        provider = DeepSeekProvider(config)
        self.assertEqual(provider.config.base_url, 'https://api.deepseek.com')

    def test_convert_messages_to_provider_format(self):
        """Test message conversion to DeepSeek format"""
        provider = DeepSeekProvider(self.config)
        messages = [
            Message(role=MessageRole.SYSTEM, content='You are helpful'),
            Message(role=MessageRole.USER, content='Hello'),
            Message(role=MessageRole.ASSISTANT, content='Hi there')
        ]

        result = provider._convert_messages_to_provider_format(messages)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['role'], 'system')
        self.assertEqual(result[0]['content'], 'You are helpful')
        self.assertEqual(result[1]['role'], 'user')
        self.assertEqual(result[1]['content'], 'Hello')
        self.assertEqual(result[2]['role'], 'assistant')
        self.assertEqual(result[2]['content'], 'Hi there')

    def test_parse_provider_response_basic(self):
        """Test parsing basic DeepSeek API response"""
        provider = DeepSeekProvider(self.config)
        response = {
            'choices': [{
                'message': {
                    'content': 'Hello! How can I help you?'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 8,
                'total_tokens': 18
            },
            'model': 'deepseek-chat'
        }

        result = provider._parse_provider_response(response, 'deepseek-chat')

        self.assertEqual(result.content, 'Hello! How can I help you?')
        self.assertEqual(result.model, 'deepseek-chat')
        self.assertEqual(result.provider, 'deepseek')
        self.assertEqual(result.usage.input_tokens, 10)
        self.assertEqual(result.usage.output_tokens, 8)
        self.assertEqual(result.usage.total_tokens, 18)
        self.assertEqual(result.finish_reason, 'stop')
        self.assertIsNone(result.raw_response.get('reasoning_content'))

    def test_parse_provider_response_with_reasoning(self):
        """Test parsing DeepSeek API response with reasoning content"""
        provider = DeepSeekProvider(self.config)
        response = {
            'choices': [{
                'message': {
                    'content': 'The answer is 42.',
                    'reasoning_content': 'Let me think about this... First, I need to consider...'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 20,
                'completion_tokens': 50,
                'total_tokens': 70
            },
            'model': 'deepseek-reasoner'
        }

        result = provider._parse_provider_response(response, 'deepseek-reasoner')

        self.assertEqual(result.content, 'The answer is 42.')
        self.assertEqual(result.model, 'deepseek-reasoner')
        self.assertEqual(result.raw_response['reasoning_content'], 'Let me think about this... First, I need to consider...')

    def test_calculate_cost(self):
        """Test cost calculation"""
        provider = DeepSeekProvider(self.config)
        # 1000 input tokens, 500 output tokens
        # Cost: (1000/1000 * 0.28) + (500/1000 * 0.42) = 0.28 + 0.21 = 0.49
        cost = provider._calculate_cost(1000, 500)
        self.assertAlmostEqual(cost, 0.49, places=2)

    @patch('urllib.request.urlopen')
    def test_complete_success(self, mock_urlopen):
        """Test successful text completion"""
        provider = DeepSeekProvider(self.config)

        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'choices': [{
                'message': {'content': 'Test response'},
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 5,
                'completion_tokens': 10,
                'total_tokens': 15
            },
            'model': 'deepseek-chat'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        messages = [Message(role=MessageRole.USER, content='Hello')]
        result = provider.complete(messages)

        self.assertEqual(result.content, 'Test response')
        self.assertEqual(result.model, 'deepseek-chat')
        self.assertEqual(result.usage.input_tokens, 5)
        self.assertEqual(result.usage.output_tokens, 10)

    @patch('urllib.request.urlopen')
    def test_complete_with_reasoner(self, mock_urlopen):
        """Test completion with deepseek-reasoner model"""
        provider = DeepSeekProvider(self.config)

        # Mock API response with reasoning content
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'choices': [{
                'message': {
                    'content': 'Final answer',
                    'reasoning_content': 'Chain of thought...'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 30,
                'total_tokens': 40
            },
            'model': 'deepseek-reasoner'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        messages = [Message(role=MessageRole.USER, content='Solve this')]
        result = provider.complete(messages, model='deepseek-reasoner')

        self.assertEqual(result.content, 'Final answer')
        self.assertEqual(result.model, 'deepseek-reasoner')
        self.assertIn('reasoning_content', result.raw_response)
        self.assertEqual(result.raw_response['reasoning_content'], 'Chain of thought...')

    @patch('urllib.request.urlopen')
    def test_complete_authentication_error(self, mock_urlopen):
        """Test authentication error handling"""
        provider = DeepSeekProvider(self.config)

        # Mock 401 error
        import urllib.error
        error_response = MagicMock()
        error_response.read.return_value = json.dumps({
            'error': {'message': 'Invalid API key'}
        }).encode('utf-8')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'url', 401, 'Unauthorized', {}, error_response
        )

        messages = [Message(role=MessageRole.USER, content='Hello')]
        with self.assertRaises(AuthenticationError) as ctx:
            provider.complete(messages)
        self.assertIn('authentication failed', str(ctx.exception).lower())

    @patch('urllib.request.urlopen')
    def test_complete_rate_limit_error(self, mock_urlopen):
        """Test rate limit error handling"""
        provider = DeepSeekProvider(self.config)

        # Mock 429 error
        import urllib.error
        error_response = MagicMock()
        error_response.read.return_value = json.dumps({
            'error': {'message': 'Rate limit exceeded'}
        }).encode('utf-8')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'url', 429, 'Too Many Requests', {}, error_response
        )

        messages = [Message(role=MessageRole.USER, content='Hello')]
        with self.assertRaises(RateLimitError) as ctx:
            provider.complete(messages)
        self.assertIn('rate limit', str(ctx.exception).lower())

    @patch('urllib.request.urlopen')
    def test_complete_invalid_request_error(self, mock_urlopen):
        """Test invalid request error handling"""
        provider = DeepSeekProvider(self.config)

        # Mock 400 error
        import urllib.error
        error_response = MagicMock()
        error_response.read.return_value = json.dumps({
            'error': {'message': 'Invalid request'}
        }).encode('utf-8')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'url', 400, 'Bad Request', {}, error_response
        )

        messages = [Message(role=MessageRole.USER, content='Hello')]
        with self.assertRaises(InvalidRequestError) as ctx:
            provider.complete(messages)
        self.assertIn('invalid request', str(ctx.exception).lower())

    @patch('urllib.request.urlopen')
    def test_complete_timeout_error(self, mock_urlopen):
        """Test timeout error handling"""
        provider = DeepSeekProvider(self.config)

        # Mock timeout
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError('timeout')

        messages = [Message(role=MessageRole.USER, content='Hello')]
        with self.assertRaises(LLMTimeoutError) as ctx:
            provider.complete(messages)
        self.assertIn('timeout', str(ctx.exception).lower())

    def test_complete_unsupported_model(self):
        """Test error on unsupported model"""
        provider = DeepSeekProvider(self.config)
        messages = [Message(role=MessageRole.USER, content='Hello')]

        with self.assertRaises(InvalidRequestError) as ctx:
            provider.complete(messages, model='unsupported-model')
        self.assertIn('not supported', str(ctx.exception).lower())

    def test_complete_with_vision_not_supported(self):
        """Test that vision is not supported"""
        provider = DeepSeekProvider(self.config)
        messages = [Message(role=MessageRole.USER, content='What is in this image?')]
        images = [ImageInput(base64='base64data')]

        with self.assertRaises(InvalidRequestError) as ctx:
            provider.complete_with_vision(messages, images)
        self.assertIn('do not support vision', str(ctx.exception).lower())

    def test_get_reasoning_content(self):
        """Test extracting reasoning content from response"""
        provider = DeepSeekProvider(self.config)

        # Response with reasoning content
        response_with_reasoning = LLMResponse(
            content='Answer',
            model='deepseek-reasoner',
            usage=TokenUsage(10, 20, 30),
            cost=0.01,
            provider='deepseek',
            raw_response={'reasoning_content': 'Chain of thought...'}
        )
        reasoning = provider.get_reasoning_content(response_with_reasoning)
        self.assertEqual(reasoning, 'Chain of thought...')

        # Response without reasoning content
        response_without_reasoning = LLMResponse(
            content='Answer',
            model='deepseek-chat',
            usage=TokenUsage(10, 20, 30),
            cost=0.01,
            provider='deepseek',
            raw_response={}
        )
        reasoning = provider.get_reasoning_content(response_without_reasoning)
        self.assertIsNone(reasoning)

    @patch('urllib.request.urlopen')
    def test_test_connection_success(self, mock_urlopen):
        """Test successful connection test"""
        provider = DeepSeekProvider(self.config)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'choices': [{
                'message': {'content': 'Hi'},
                'finish_reason': 'stop'
            }],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
            'model': 'deepseek-chat'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success, message = provider.test_connection()
        self.assertTrue(success)
        self.assertIn('deepseek-chat', message.lower())

    @patch('urllib.request.urlopen')
    def test_test_connection_failure(self, mock_urlopen):
        """Test failed connection test"""
        provider = DeepSeekProvider(self.config)

        # Mock error
        import urllib.error
        error_response = MagicMock()
        error_response.read.return_value = json.dumps({
            'error': {'message': 'Auth failed'}
        }).encode('utf-8')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'url', 401, 'Unauthorized', {}, error_response
        )

        success, message = provider.test_connection()
        self.assertFalse(success)
        self.assertIn('failed', message.lower())

    @patch('urllib.request.urlopen')
    def test_complete_with_temperature_chat_model(self, mock_urlopen):
        """Test that temperature is included for deepseek-chat"""
        provider = DeepSeekProvider(self.config)

        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'choices': [{'message': {'content': 'Test'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5, 'total_tokens': 10},
            'model': 'deepseek-chat'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        messages = [Message(role=MessageRole.USER, content='Hello')]
        provider.complete(messages, model='deepseek-chat', temperature=0.5)

        # Verify temperature was included in request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload['temperature'], 0.5)

    @patch('urllib.request.urlopen')
    def test_complete_without_temperature_reasoner_model(self, mock_urlopen):
        """Test that temperature is NOT included for deepseek-reasoner"""
        provider = DeepSeekProvider(self.config)

        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'choices': [{'message': {'content': 'Test'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5, 'total_tokens': 10},
            'model': 'deepseek-reasoner'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        messages = [Message(role=MessageRole.USER, content='Hello')]
        provider.complete(messages, model='deepseek-reasoner', temperature=0.5)

        # Verify temperature was NOT included in request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertNotIn('temperature', payload)


if __name__ == '__main__':
    unittest.main()
