"""
LiteLLM Provider Implementation

Unified provider for 100+ LLM models through the LiteLLM library.
Supports text and vision capabilities with automatic model routing.
"""

import json
import sys
import os
from typing import List, Optional, Dict, Any

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
    InvalidRequestError,
    ProviderError
)
from lib.llm_config import ProviderConfig

# Try to import litellm
try:
    import litellm
    from litellm import completion
    from litellm.exceptions import (
        RateLimitError as LiteLLMRateLimitError,
        Timeout as LiteLLMTimeout,
        AuthenticationError as LiteLLMAuthenticationError,
        BadRequestError as LiteLLMBadRequestError
    )
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not installed. Run: pip install litellm", file=sys.stderr)


class LiteLLMProvider(LLMProvider):
    """
    LiteLLM provider for unified access to 100+ LLM models

    Supported providers through LiteLLM:
    - OpenAI (gpt-4o, gpt-4o-mini, o3-mini, etc.)
    - Anthropic (claude-3.5-sonnet, claude-3-haiku, etc.)
    - Google (gemini-2.0-flash, gemini-2.0-pro, etc.)
    - DeepSeek (deepseek-chat, deepseek-r1, etc.)
    - Groq, Together, Mistral, Cohere, and 90+ more
    """

    # Vision-capable models (partial list - LiteLLM supports many more)
    VISION_MODELS = {
        'gpt-4o', 'gpt-4o-mini', 'gpt-4-vision-preview',
        'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
        'gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-pro-vision',
        'llava-v1.6-34b', 'llava-v1.5-7b'
    }

    def __init__(self, config: ProviderConfig):
        """Initialize LiteLLM provider"""
        super().__init__(config)

        if not LITELLM_AVAILABLE:
            raise ImportError(
                "litellm library not installed. Install with: pip install litellm"
            )

        self._validate_config()
        self._configure_litellm()

    def _validate_config(self):
        """Validate LiteLLM-specific configuration"""
        # LiteLLM uses environment variables for most providers
        # So API key in config is optional - providers can be configured via env

        if not self.config.default_model:
            # Default to a reliable, cheap model
            self.config.default_model = 'gpt-4o-mini'

    def _configure_litellm(self):
        """Configure LiteLLM global settings"""
        # Set timeout
        litellm.request_timeout = self.config.timeout

        # Enable verbose logging if debug mode
        if os.getenv('LITELLM_DEBUG', 'false').lower() == 'true':
            litellm.set_verbose = True

        # Configure retries (we handle retries in base class, so disable LiteLLM's)
        litellm.num_retries = 0

        # Set API keys from config if provided
        extra_settings = self.config.extra_settings or {}

        # Map common provider API keys
        if extra_settings.get('openai_api_key'):
            os.environ['OPENAI_API_KEY'] = extra_settings['openai_api_key']
        if extra_settings.get('anthropic_api_key'):
            os.environ['ANTHROPIC_API_KEY'] = extra_settings['anthropic_api_key']
        if extra_settings.get('google_api_key'):
            os.environ['GOOGLE_API_KEY'] = extra_settings['google_api_key']
        if extra_settings.get('deepseek_api_key'):
            os.environ['DEEPSEEK_API_KEY'] = extra_settings['deepseek_api_key']

    def _convert_messages_to_provider_format(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert standard messages to LiteLLM format

        LiteLLM uses OpenAI-compatible format:
        [{"role": "user", "content": "..."}]
        """
        litellm_messages = []

        for msg in messages:
            litellm_msg = {
                'role': msg.role.value,
                'content': msg.content
            }
            litellm_messages.append(litellm_msg)

        return litellm_messages

    def _convert_images_to_content_parts(
        self,
        text: str,
        images: List[ImageInput]
    ) -> List[Dict[str, Any]]:
        """
        Convert text and images to multi-modal content array

        Format: [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "..."}}
        ]
        """
        content_parts = [{'type': 'text', 'text': text}]

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
                # Read and base64 encode
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

    def _parse_provider_response(self, response: Any, model: str) -> LLMResponse:
        """
        Parse LiteLLM response to standard format

        LiteLLM returns ModelResponse object with:
        - choices[0].message.content
        - usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
        - model
        - _hidden_params.custom_llm_provider (actual provider used)
        """
        try:
            # Extract content
            content = response.choices[0].message.content

            # Extract usage
            usage_data = response.usage
            input_tokens = usage_data.prompt_tokens if usage_data else 0
            output_tokens = usage_data.completion_tokens if usage_data else 0
            total_tokens = usage_data.total_tokens if usage_data else (input_tokens + output_tokens)

            # Calculate cost using LiteLLM's cost calculator
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                # Fallback to config-based calculation
                cost = self._calculate_cost(input_tokens, output_tokens)

            usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens
            )

            # Extract actual provider used (e.g., 'openai', 'anthropic', etc.)
            actual_provider = 'litellm'
            if hasattr(response, '_hidden_params'):
                actual_provider = response._hidden_params.get('custom_llm_provider', 'litellm')

            # Extract model
            response_model = response.model if hasattr(response, 'model') else model

            # Extract finish reason
            finish_reason = None
            if response.choices and len(response.choices) > 0:
                finish_reason = response.choices[0].finish_reason

            return LLMResponse(
                content=content,
                model=response_model,
                usage=usage,
                cost=cost,
                provider=f"litellm/{actual_provider}",
                finish_reason=finish_reason,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )
        except Exception as e:
            raise ProviderError(f"Failed to parse LiteLLM response: {str(e)}")

    def _map_litellm_exceptions(self, e: Exception):
        """Map LiteLLM exceptions to our standard exceptions"""
        if not LITELLM_AVAILABLE:
            raise ProviderError(str(e))

        if isinstance(e, LiteLLMRateLimitError):
            raise RateLimitError(f"LiteLLM rate limit: {str(e)}")
        elif isinstance(e, LiteLLMTimeout):
            raise LLMTimeoutError(f"LiteLLM timeout: {str(e)}")
        elif isinstance(e, LiteLLMAuthenticationError):
            raise AuthenticationError(f"LiteLLM authentication failed: {str(e)}")
        elif isinstance(e, LiteLLMBadRequestError):
            raise InvalidRequestError(f"LiteLLM bad request: {str(e)}")
        else:
            raise ProviderError(f"LiteLLM error: {str(e)}")

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Complete a text-only conversation via LiteLLM

        Args:
            messages: List of Message objects
            model: Model identifier (e.g., 'gpt-4o', 'claude-3.5-sonnet')
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional LiteLLM parameters

        Returns:
            LLMResponse with standardized format
        """
        model = model or self.config.default_model

        # Convert messages
        litellm_messages = self._convert_messages_to_provider_format(messages)

        # Build request parameters
        request_params = {
            'model': model,
            'messages': litellm_messages,
            'temperature': temperature,
        }

        if max_tokens:
            request_params['max_tokens'] = max_tokens
        elif self.config.max_tokens:
            request_params['max_tokens'] = self.config.max_tokens

        # Add custom kwargs
        request_params.update(kwargs)

        # Make API call (with retry logic from base class)
        def _call():
            try:
                return completion(**request_params)
            except Exception as e:
                self._map_litellm_exceptions(e)

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
        """
        Complete a conversation with vision inputs via LiteLLM

        Args:
            messages: List of Message objects
            images: List of ImageInput objects
            model: Model identifier (must support vision)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional LiteLLM parameters

        Returns:
            LLMResponse with standardized format
        """
        model = model or self.config.default_model

        # Validate model supports vision (basic check)
        model_base = model.split(':')[0]  # Handle 'provider/model' format
        if model_base not in self.VISION_MODELS and not any(vm in model for vm in self.VISION_MODELS):
            print(
                f"Warning: Model {model} may not support vision. "
                f"Proceeding anyway, but may fail.",
                file=sys.stderr
            )

        # Convert messages
        litellm_messages = self._convert_messages_to_provider_format(messages)

        # Add images to the last user message
        if litellm_messages and litellm_messages[-1]['role'] == 'user':
            text_content = litellm_messages[-1]['content']
            litellm_messages[-1]['content'] = self._convert_images_to_content_parts(
                text_content, images
            )
        else:
            raise InvalidRequestError("Last message must be from user for vision requests")

        # Build request parameters
        request_params = {
            'model': model,
            'messages': litellm_messages,
            'temperature': temperature,
        }

        if max_tokens:
            request_params['max_tokens'] = max_tokens
        elif self.config.max_tokens:
            request_params['max_tokens'] = self.config.max_tokens

        # Add custom kwargs
        request_params.update(kwargs)

        # Make API call (with retry logic from base class)
        def _call():
            try:
                return completion(**request_params)
            except Exception as e:
                self._map_litellm_exceptions(e)

        response = self._retry_with_backoff(_call)

        # Parse and return
        return self._parse_provider_response(response, model)

    def test_connection(self, model: Optional[str] = None) -> tuple[bool, str]:
        """
        Test connection with a lightweight API call

        Args:
            model: Specific model to test (uses default if not specified)

        Returns:
            Tuple of (success: bool, message: str)
        """
        test_model = model or self.config.default_model

        try:
            test_message = Message(
                role=MessageRole.USER,
                content="Hi"
            )
            response = self.complete([test_message], model=test_model, max_tokens=5)
            return True, f"Successfully connected via LiteLLM. Model: {response.model}, Provider: {response.provider}"
        except Exception as e:
            return False, f"Connection test failed for {test_model}: {str(e)}"

    @staticmethod
    def list_available_models(provider: Optional[str] = None) -> List[str]:
        """
        List available models through LiteLLM

        Args:
            provider: Filter by provider (e.g., 'openai', 'anthropic')

        Returns:
            List of model identifiers
        """
        if not LITELLM_AVAILABLE:
            return []

        try:
            # Get all models from LiteLLM
            all_models = litellm.model_list

            if provider:
                # Filter by provider
                return [m for m in all_models if m.startswith(f"{provider}/") or provider in m]

            return all_models
        except Exception:
            # Fallback to known models
            known_models = [
                'gpt-4o', 'gpt-4o-mini', 'o3-mini',
                'claude-3.5-sonnet', 'claude-3-haiku',
                'gemini-2.0-flash', 'gemini-2.0-pro',
                'deepseek-chat', 'deepseek-r1'
            ]

            if provider:
                return [m for m in known_models if provider in m]

            return known_models


def main():
    """CLI interface for testing LiteLLM provider"""
    import argparse
    from lib.llm_config import LLMConfigManager

    parser = argparse.ArgumentParser(description='Test LiteLLM provider')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # test command
    test_parser = subparsers.add_parser('test', help='Test connection')
    test_parser.add_argument('--model', type=str, default=None, help='Model to test')

    # complete command
    complete_parser = subparsers.add_parser('complete', help='Complete a prompt')
    complete_parser.add_argument('prompt', type=str, help='Prompt to send')
    complete_parser.add_argument('--model', type=str, default=None, help='Model to use')
    complete_parser.add_argument('--max-tokens', type=int, default=100, help='Max tokens')

    # vision command
    vision_parser = subparsers.add_parser('vision', help='Test vision capabilities')
    vision_parser.add_argument('prompt', type=str, help='Prompt to send')
    vision_parser.add_argument('--image', type=str, required=True, help='Image file path')
    vision_parser.add_argument('--model', type=str, default='gpt-4o', help='Model to use')

    # list-models command
    list_parser = subparsers.add_parser('list-models', help='List available models')
    list_parser.add_argument('--provider', type=str, default=None, help='Filter by provider')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'list-models':
        models = LiteLLMProvider.list_available_models(args.provider)
        print(f"Available models{f' for {args.provider}' if args.provider else ''}:")
        for model in models:
            print(f"  - {model}")
        return 0

    # Load config
    config_manager = LLMConfigManager()
    litellm_config = config_manager.get_provider('litellm')

    if not litellm_config:
        print("Error: LiteLLM provider not configured")
        print("Configure in ~/.claude-loop/providers.yaml or set environment variables")
        return 1

    # Create provider
    try:
        provider = LiteLLMProvider(litellm_config)
    except Exception as e:
        print(f"Error creating provider: {e}")
        return 1

    if args.command == 'test':
        print(f"Testing connection to LiteLLM ({args.model or litellm_config.default_model})...")
        success, message = provider.test_connection(model=args.model)
        if success:
            print(f"✓ {message}")
            return 0
        else:
            print(f"✗ {message}")
            return 1

    elif args.command == 'complete':
        print(f"Sending prompt to {args.model or litellm_config.default_model}...")
        message = Message(role=MessageRole.USER, content=args.prompt)

        try:
            response = provider.complete(
                [message],
                model=args.model,
                max_tokens=args.max_tokens
            )

            print(f"\nResponse: {response.content}")
            print(f"\nUsage:")
            print(f"  Model: {response.model}")
            print(f"  Provider: {response.provider}")
            print(f"  Input tokens: {response.usage.input_tokens}")
            print(f"  Output tokens: {response.usage.output_tokens}")
            print(f"  Cost: ${response.cost:.6f}")

            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

    elif args.command == 'vision':
        print(f"Sending vision request to {args.model}...")
        message = Message(role=MessageRole.USER, content=args.prompt)
        image = ImageInput(file_path=args.image)

        try:
            response = provider.complete_with_vision(
                [message],
                [image],
                model=args.model
            )

            print(f"\nResponse: {response.content}")
            print(f"\nUsage:")
            print(f"  Model: {response.model}")
            print(f"  Provider: {response.provider}")
            print(f"  Input tokens: {response.usage.input_tokens}")
            print(f"  Output tokens: {response.usage.output_tokens}")
            print(f"  Cost: ${response.cost:.6f}")

            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
