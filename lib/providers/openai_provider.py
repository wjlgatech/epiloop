"""
OpenAI Provider Implementation

Supports GPT-4o, GPT-4o-mini, and o3-mini models with text and vision capabilities.
"""

import json
import time
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


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4o provider implementation"""

    # Supported models
    SUPPORTED_MODELS = {
        'gpt-4o': {'supports_vision': True, 'max_tokens': 128000},
        'gpt-4o-mini': {'supports_vision': True, 'max_tokens': 128000},
        'o3-mini': {'supports_vision': False, 'max_tokens': 128000}
    }

    def __init__(self, config: ProviderConfig):
        """Initialize OpenAI provider"""
        super().__init__(config)
        self._validate_config()

    def _validate_config(self):
        """Validate OpenAI-specific configuration"""
        if not self.config.api_key or self.config.api_key == 'disabled':
            raise AuthenticationError("OpenAI API key is required")

        if not self.config.base_url:
            self.config.base_url = "https://api.openai.com/v1"

    def _convert_messages_to_provider_format(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert standard messages to OpenAI format"""
        openai_messages = []

        for msg in messages:
            openai_msg = {
                'role': msg.role.value,
                'content': msg.content
            }
            openai_messages.append(openai_msg)

        return openai_messages

    def _convert_images_to_provider_format(self, images: List[ImageInput]) -> List[Dict[str, Any]]:
        """Convert images to OpenAI vision format"""
        content_parts = []

        for image in images:
            if image.base64:
                image_part = {
                    'type': 'image_url',
                    'image_url': {
                        'url': f"data:{image.mime_type};base64,{image.base64}"
                    }
                }
            elif image.url:
                image_part = {
                    'type': 'image_url',
                    'image_url': {
                        'url': image.url
                    }
                }
            else:  # file_path
                # For file paths, we need to read and base64 encode
                import base64
                with open(image.file_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                image_part = {
                    'type': 'image_url',
                    'image_url': {
                        'url': f"data:{image.mime_type};base64,{image_data}"
                    }
                }

            content_parts.append(image_part)

        return content_parts

    def _parse_provider_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse OpenAI API response to standard format"""
        # Extract content
        content = response['choices'][0]['message']['content']

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
        model = response.get('model', 'gpt-4o')
        finish_reason = response['choices'][0].get('finish_reason')

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            cost=cost,
            provider='openai',
            finish_reason=finish_reason,
            raw_response=response
        )

    def _make_api_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to OpenAI API"""
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

            # Map OpenAI error codes to our exceptions
            if e.code == 401 or e.code == 403:
                raise AuthenticationError(f"OpenAI authentication failed: {error_message}")
            elif e.code == 429:
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_message}")
            elif e.code == 400:
                raise InvalidRequestError(f"OpenAI invalid request: {error_message}")
            else:
                raise InvalidRequestError(f"OpenAI API error ({e.code}): {error_message}")
        except urllib.error.URLError as e:
            raise LLMTimeoutError(f"OpenAI API timeout or network error: {str(e)}")

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Complete a text-only conversation"""
        model = model or self.config.default_model

        # Validate model
        if model not in self.SUPPORTED_MODELS:
            raise InvalidRequestError(f"Model {model} not supported. Supported: {list(self.SUPPORTED_MODELS.keys())}")

        # Convert messages
        openai_messages = self._convert_messages_to_provider_format(messages)

        # Build request payload
        payload = {
            'model': model,
            'messages': openai_messages,
            'temperature': temperature
        }

        if max_tokens:
            payload['max_tokens'] = max_tokens
        elif self.config.max_tokens:
            payload['max_tokens'] = self.config.max_tokens

        # Make API call (with retry logic from base class)
        def _call():
            return self._make_api_call(payload)

        response = self._retry_with_backoff(_call)

        # Parse and return
        return self._parse_provider_response(response)

    def complete_with_vision(
        self,
        messages: List[Message],
        images: List[ImageInput],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Complete a conversation with vision inputs"""
        model = model or self.config.default_model

        # Validate model supports vision
        if model not in self.SUPPORTED_MODELS:
            raise InvalidRequestError(f"Model {model} not supported")
        if not self.SUPPORTED_MODELS[model]['supports_vision']:
            raise InvalidRequestError(f"Model {model} does not support vision")

        # Convert messages
        openai_messages = self._convert_messages_to_provider_format(messages)

        # Add images to the last user message
        if openai_messages and openai_messages[-1]['role'] == 'user':
            # Convert content to multi-part format
            text_content = openai_messages[-1]['content']
            image_parts = self._convert_images_to_provider_format(images)

            openai_messages[-1]['content'] = [
                {'type': 'text', 'text': text_content},
                *image_parts
            ]
        else:
            raise InvalidRequestError("Last message must be from user for vision requests")

        # Build request payload
        payload = {
            'model': model,
            'messages': openai_messages,
            'temperature': temperature
        }

        if max_tokens:
            payload['max_tokens'] = max_tokens
        elif self.config.max_tokens:
            payload['max_tokens'] = self.config.max_tokens

        # Make API call (with retry logic from base class)
        def _call():
            return self._make_api_call(payload)

        response = self._retry_with_backoff(_call)

        # Parse and return
        return self._parse_provider_response(response)

    def test_connection(self) -> tuple[bool, str]:
        """Test connection with a lightweight API call"""
        try:
            test_message = Message(
                role=MessageRole.USER,
                content="Hello"
            )
            response = self.complete([test_message], max_tokens=5)
            return True, f"Successfully connected to OpenAI. Model: {response.model}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


def main():
    """CLI interface for testing OpenAI provider"""
    import argparse
    from lib.llm_config import LLMConfigManager

    parser = argparse.ArgumentParser(description='Test OpenAI provider')
    parser.add_argument('command', choices=['test', 'complete', 'vision'],
                        help='Command to run')
    parser.add_argument('--prompt', type=str, default='Hello, how are you?',
                        help='Prompt to send')
    parser.add_argument('--model', type=str, default=None,
                        help='Model to use')
    parser.add_argument('--image', type=str, default=None,
                        help='Image file path for vision test')

    args = parser.parse_args()

    # Load config
    config_manager = LLMConfigManager()
    openai_config = config_manager.get_provider('openai')

    if not openai_config:
        print("Error: OpenAI provider not configured")
        sys.exit(1)

    # Create provider
    provider = OpenAIProvider(openai_config)

    if args.command == 'test':
        print(f"Testing connection to OpenAI ({openai_config.default_model})...")
        success, message = provider.test_connection()
        if success:
            print(f"✓ {message}")
            sys.exit(0)
        else:
            print(f"✗ {message}")
            sys.exit(1)

    elif args.command == 'complete':
        print(f"Sending prompt to {args.model or openai_config.default_model}...")
        message = Message(role=MessageRole.USER, content=args.prompt)
        response = provider.complete([message], model=args.model)

        print(f"\nResponse: {response.content}")
        print(f"\nUsage:")
        print(f"  Input tokens: {response.usage.input_tokens}")
        print(f"  Output tokens: {response.usage.output_tokens}")
        print(f"  Cost: ${response.cost:.6f}")

    elif args.command == 'vision':
        if not args.image:
            print("Error: --image required for vision command")
            sys.exit(1)

        print(f"Sending vision request to {args.model or openai_config.default_model}...")
        message = Message(role=MessageRole.USER, content=args.prompt)
        image = ImageInput(file_path=args.image)

        response = provider.complete_with_vision([message], [image], model=args.model)

        print(f"\nResponse: {response.content}")
        print(f"\nUsage:")
        print(f"  Input tokens: {response.usage.input_tokens}")
        print(f"  Output tokens: {response.usage.output_tokens}")
        print(f"  Cost: ${response.cost:.6f}")


if __name__ == '__main__':
    main()
