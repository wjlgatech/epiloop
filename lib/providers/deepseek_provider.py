"""
DeepSeek Provider Implementation

Supports DeepSeek-V3 (deepseek-chat) and DeepSeek-R1 (deepseek-reasoner) models.
DeepSeek-R1 includes Chain-of-Thought reasoning output in reasoning_content field.
"""

import json
from typing import List, Optional, Dict, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from lib.llm_provider import (
    LLMProvider,
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


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider implementation (OpenAI-compatible API)"""

    # Supported models
    SUPPORTED_MODELS = {
        'deepseek-chat': {'supports_vision': False, 'max_tokens': 64000, 'supports_reasoning': False},
        'deepseek-reasoner': {'supports_vision': False, 'max_tokens': 64000, 'supports_reasoning': True}
    }

    def __init__(self, config: ProviderConfig):
        """Initialize DeepSeek provider"""
        super().__init__(config)
        self._validate_config()

    def _validate_config(self):
        """Validate DeepSeek-specific configuration"""
        if not self.config.api_key or self.config.api_key == 'disabled':
            raise AuthenticationError("DeepSeek API key is required")

        if not self.config.base_url:
            self.config.base_url = "https://api.deepseek.com"

    def _convert_messages_to_provider_format(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert standard messages to DeepSeek format (OpenAI-compatible)"""
        deepseek_messages = []

        for msg in messages:
            deepseek_msg = {
                'role': msg.role.value,
                'content': msg.content
            }
            deepseek_messages.append(deepseek_msg)

        return deepseek_messages

    def _parse_provider_response(self, response: Dict[str, Any], model: str) -> LLMResponse:
        """Parse DeepSeek API response to standard format

        For deepseek-reasoner, extracts reasoning_content (CoT) if present.
        """
        # Extract message content
        message = response['choices'][0]['message']
        content = message.get('content', '')

        # Extract reasoning content if present (deepseek-reasoner only)
        reasoning_content = message.get('reasoning_content', None)

        # Extract usage
        usage_data = response.get('usage', {})
        input_tokens = usage_data.get('prompt_tokens', 0)
        output_tokens = usage_data.get('completion_tokens', 0)
        total_tokens = usage_data.get('total_tokens', input_tokens + output_tokens)

        # Calculate cost
        cost = self._calculate_cost(input_tokens, output_tokens)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )

        # Extract model and finish reason
        model = response.get('model', 'deepseek-chat')
        finish_reason = response['choices'][0].get('finish_reason')

        # Include reasoning_content in raw_response if present
        raw_response = response.copy()
        if reasoning_content:
            raw_response['reasoning_content'] = reasoning_content

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            cost=cost,
            provider='deepseek',
            finish_reason=finish_reason,
            raw_response=raw_response
        )

    def _make_api_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to DeepSeek API (OpenAI-compatible)"""
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.config.api_key}'
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            error_data = json.loads(error_body) if error_body else {}
            error_message = error_data.get('error', {}).get('message', str(e))

            # Map DeepSeek error codes to our exceptions
            if e.code == 401 or e.code == 403:
                raise AuthenticationError(f"DeepSeek authentication failed: {error_message}")
            elif e.code == 429:
                raise RateLimitError(f"DeepSeek rate limit exceeded: {error_message}")
            elif e.code == 400:
                raise InvalidRequestError(f"DeepSeek invalid request: {error_message}")
            else:
                raise InvalidRequestError(f"DeepSeek API error ({e.code}): {error_message}")
        except urllib.error.URLError as e:
            raise LLMTimeoutError(f"DeepSeek API timeout or network error: {str(e)}")

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Complete a text-only conversation

        Note: deepseek-reasoner does not support temperature, top_p, or other
        sampling parameters. These are silently ignored for that model.
        """
        model = model or self.config.default_model

        # Validate model
        if model not in self.SUPPORTED_MODELS:
            raise InvalidRequestError(f"Model {model} not supported. Supported: {list(self.SUPPORTED_MODELS.keys())}")

        # Convert messages
        deepseek_messages = self._convert_messages_to_provider_format(messages)

        # Build request payload
        payload = {
            'model': model,
            'messages': deepseek_messages
        }

        # Only add temperature for deepseek-chat (not supported by deepseek-reasoner)
        if model == 'deepseek-chat':
            payload['temperature'] = temperature

        if max_tokens:
            payload['max_tokens'] = max_tokens
        elif self.config.max_tokens:
            payload['max_tokens'] = self.config.max_tokens

        # Make API call (with retry logic from base class)
        def _call():
            return self._make_api_call(payload)

        response = self._retry_with_backoff(_call)

        # Parse and return
        return self._parse_provider_response(response, model)

    def complete_with_vision(
        self,
        messages: List[Message],
        images: List[ImageInput],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Complete a conversation with vision inputs

        DeepSeek models do not currently support vision, so this raises an error.
        """
        raise InvalidRequestError("DeepSeek models do not support vision capabilities")

    def test_connection(self) -> tuple[bool, str]:
        """Test API connectivity with a minimal request"""
        try:
            test_messages = [
                Message(role=MessageRole.USER, content="Hello")
            ]
            response = self.complete(test_messages, max_tokens=10)
            return True, f"Connected successfully. Model: {response.model}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def get_reasoning_content(self, response: LLMResponse) -> Optional[str]:
        """Extract reasoning content (Chain-of-Thought) from response

        Returns None if no reasoning content is present (e.g., for deepseek-chat).
        Only deepseek-reasoner returns reasoning_content.
        """
        if response.raw_response and 'reasoning_content' in response.raw_response:
            return response.raw_response['reasoning_content']
        return None


def main():
    """CLI interface for testing DeepSeek provider"""
    import argparse
    from lib.llm_config import LLMConfigManager

    parser = argparse.ArgumentParser(description='Test DeepSeek provider')
    parser.add_argument('command', choices=['test', 'complete', 'reasoning'],
                       help='Command to execute')
    parser.add_argument('--prompt', type=str, default='Hello, how are you?',
                       help='Prompt for completion')
    parser.add_argument('--model', type=str, default=None,
                       help='Model to use (deepseek-chat or deepseek-reasoner)')
    args = parser.parse_args()

    # Load configuration
    config_manager = LLMConfigManager()
    provider_config = config_manager.get_provider('deepseek')

    if not provider_config:
        print("Error: DeepSeek provider not configured")
        sys.exit(1)

    # Override model if specified
    if args.model:
        provider_config.default_model = args.model

    # Initialize provider
    try:
        provider = DeepSeekProvider(provider_config)
    except Exception as e:
        print(f"Error initializing provider: {e}")
        sys.exit(1)

    # Execute command
    if args.command == 'test':
        success, message = provider.test_connection()
        print(f"{'✓' if success else '✗'} {message}")
        sys.exit(0 if success else 1)

    elif args.command == 'complete':
        try:
            messages = [Message(role=MessageRole.USER, content=args.prompt)]
            response = provider.complete(messages)

            print(f"\nModel: {response.model}")
            print(f"Content: {response.content}")
            print(f"Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
            print(f"Cost: ${response.cost:.6f}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'reasoning':
        try:
            # Force deepseek-reasoner for reasoning test
            provider_config.default_model = 'deepseek-reasoner'
            provider = DeepSeekProvider(provider_config)

            messages = [Message(role=MessageRole.USER, content=args.prompt)]
            response = provider.complete(messages)

            print(f"\nModel: {response.model}")

            # Extract reasoning content
            reasoning = provider.get_reasoning_content(response)
            if reasoning:
                print(f"\n=== Chain-of-Thought Reasoning ===")
                print(reasoning)
                print(f"\n=== Final Answer ===")

            print(response.content)
            print(f"\nTokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
            print(f"Cost: ${response.cost:.6f}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
