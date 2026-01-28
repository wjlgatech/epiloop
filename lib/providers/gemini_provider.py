"""
Google Gemini Provider Implementation

Supports Gemini 2.0 Flash, Pro, and Flash-Thinking models with text and vision capabilities.
Includes Google-specific safety settings and optional grounding with Google Search.
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


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""

    # Supported models
    SUPPORTED_MODELS = {
        'gemini-2.0-flash': {'supports_vision': True, 'max_tokens': 1048576},
        'gemini-2.0-pro': {'supports_vision': True, 'max_tokens': 1048576},
        'gemini-2.0-flash-thinking': {'supports_vision': True, 'max_tokens': 32768}
    }

    # Safety settings for harmful content filtering
    DEFAULT_SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ]

    def __init__(self, config: ProviderConfig):
        """Initialize Gemini provider"""
        super().__init__(config)
        self._validate_config()

    def _validate_config(self):
        """Validate Gemini-specific configuration"""
        if not self.config.api_key or self.config.api_key == 'disabled':
            raise AuthenticationError("Gemini API key is required")

        if not self.config.base_url:
            self.config.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _convert_messages_to_provider_format(self, messages: List[Message]) -> Dict[str, Any]:
        """Convert standard messages to Gemini format

        Gemini uses a different format than OpenAI:
        - Separate system instruction (not part of messages)
        - Messages have 'role' (user/model) and 'parts' array
        """
        gemini_contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System messages become system_instruction (only first one)
                if system_instruction is None:
                    system_instruction = msg.content
            else:
                # Convert role
                role = "user" if msg.role == MessageRole.USER else "model"

                # Create parts array
                parts = [{"text": msg.content}]

                gemini_contents.append({
                    "role": role,
                    "parts": parts
                })

        return {
            "contents": gemini_contents,
            "system_instruction": system_instruction
        }

    def _convert_images_to_provider_format(self, images: List[ImageInput]) -> List[Dict[str, Any]]:
        """Convert images to Gemini vision format

        Gemini supports inline_data (base64) and fileData references
        """
        parts = []

        for image in images:
            if image.base64:
                # Inline base64 data
                parts.append({
                    "inline_data": {
                        "mime_type": image.mime_type,
                        "data": image.base64
                    }
                })
            elif image.url:
                # For URLs, we need to fetch and encode (or use fileData API)
                # For now, we'll fetch and convert to base64
                import urllib.request
                import base64

                try:
                    with urllib.request.urlopen(image.url, timeout=30) as response:
                        image_data = base64.b64encode(response.read()).decode('utf-8')
                        parts.append({
                            "inline_data": {
                                "mime_type": image.mime_type,
                                "data": image_data
                            }
                        })
                except Exception as e:
                    raise InvalidRequestError(f"Failed to fetch image from URL: {str(e)}")
            elif image.file_path:  # file_path
                # For file paths, read and base64 encode
                import base64
                try:
                    with open(image.file_path, 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                    parts.append({
                        "inline_data": {
                            "mime_type": image.mime_type,
                            "data": image_data
                        }
                    })
                except Exception as e:
                    raise InvalidRequestError(f"Failed to read image file: {str(e)}")

        return parts

    def _parse_provider_response(self, response: Dict[str, Any], model: str) -> LLMResponse:
        """Parse Gemini API response to standard format"""
        # Extract content
        candidates = response.get('candidates', [])
        if not candidates:
            raise InvalidRequestError("No candidates in Gemini response")

        candidate = candidates[0]
        content_parts = candidate.get('content', {}).get('parts', [])

        if not content_parts:
            # Check if blocked by safety filter
            finish_reason = candidate.get('finishReason', 'UNKNOWN')
            if finish_reason in ['SAFETY', 'PROHIBITED_CONTENT']:
                safety_ratings = candidate.get('safetyRatings', [])
                raise InvalidRequestError(f"Content blocked by safety filter: {finish_reason}. Ratings: {safety_ratings}")
            raise InvalidRequestError("No content in Gemini response")

        # Combine all text parts
        content = ''.join(part.get('text', '') for part in content_parts)

        # Extract usage metadata
        usage_metadata = response.get('usageMetadata', {})
        input_tokens = usage_metadata.get('promptTokenCount', 0)
        output_tokens = usage_metadata.get('candidatesTokenCount', 0)
        total_tokens = usage_metadata.get('totalTokenCount', input_tokens + output_tokens)

        # Calculate cost
        cost = self._calculate_cost(input_tokens, output_tokens)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )

        # Extract finish reason
        finish_reason = candidate.get('finishReason', 'STOP')

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            cost=cost,
            provider='gemini',
            finish_reason=finish_reason,
            raw_response=response
        )

    def _make_api_call(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Gemini API"""
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/{endpoint}?key={self.config.api_key}"
        headers = {
            'Content-Type': 'application/json'
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body) if error_body else {}
                error_message = error_data.get('error', {}).get('message', str(e))
            except (json.JSONDecodeError, KeyError, TypeError) as json_err:
                # SAFETY: Catch specific exceptions instead of bare except
                error_message = error_body or str(e)

            # Map Gemini error codes to our exceptions
            if e.code == 401 or e.code == 403:
                raise AuthenticationError(f"Gemini authentication failed: {error_message}")
            elif e.code == 429:
                raise RateLimitError(f"Gemini rate limit exceeded: {error_message}")
            elif e.code == 400:
                raise InvalidRequestError(f"Gemini invalid request: {error_message}")
            else:
                raise InvalidRequestError(f"Gemini API error ({e.code}): {error_message}")
        except urllib.error.URLError as e:
            raise LLMTimeoutError(f"Gemini API timeout or network error: {str(e)}")

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        safety_settings: Optional[List[Dict]] = None,
        enable_grounding: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Complete a text-only conversation

        Args:
            messages: List of Message objects
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            safety_settings: Custom safety settings (uses defaults if not provided)
            enable_grounding: Enable Google Search grounding (optional)
            **kwargs: Additional provider-specific parameters
        """
        model = model or self.config.default_model

        # Validate model
        if model not in self.SUPPORTED_MODELS:
            raise InvalidRequestError(f"Model {model} not supported. Supported: {list(self.SUPPORTED_MODELS.keys())}")

        # Convert messages
        message_data = self._convert_messages_to_provider_format(messages)

        # Build generation config
        generation_config = {
            'temperature': temperature
        }

        if max_tokens:
            generation_config['maxOutputTokens'] = max_tokens
        elif self.config.max_tokens:
            generation_config['maxOutputTokens'] = self.config.max_tokens

        # Build request payload
        payload = {
            'contents': message_data['contents'],
            'generationConfig': generation_config,
            'safetySettings': safety_settings or self.DEFAULT_SAFETY_SETTINGS
        }

        # Add system instruction if present
        if message_data['system_instruction']:
            payload['systemInstruction'] = {
                'parts': [{'text': message_data['system_instruction']}]
            }

        # Add grounding if enabled
        if enable_grounding:
            payload['tools'] = [{
                'googleSearchRetrieval': {}
            }]

        # Make API call (with retry logic from base class)
        endpoint = f"models/{model}:generateContent"

        def _call():
            return self._make_api_call(endpoint, payload)

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
        safety_settings: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """Complete a conversation with vision inputs

        Args:
            messages: List of Message objects
            images: List of ImageInput objects
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            safety_settings: Custom safety settings (uses defaults if not provided)
            **kwargs: Additional provider-specific parameters
        """
        model = model or self.config.default_model

        # Validate model supports vision
        if model not in self.SUPPORTED_MODELS:
            raise InvalidRequestError(f"Model {model} not supported")
        if not self.SUPPORTED_MODELS[model]['supports_vision']:
            raise InvalidRequestError(f"Model {model} does not support vision")

        # Convert messages
        message_data = self._convert_messages_to_provider_format(messages)

        # Add images to the last user message
        contents = message_data['contents']
        if contents and contents[-1]['role'] == 'user':
            # Add image parts to the existing user message
            image_parts = self._convert_images_to_provider_format(images)
            contents[-1]['parts'].extend(image_parts)
        else:
            raise InvalidRequestError("Last message must be from user for vision requests")

        # Build generation config
        generation_config = {
            'temperature': temperature
        }

        if max_tokens:
            generation_config['maxOutputTokens'] = max_tokens
        elif self.config.max_tokens:
            generation_config['maxOutputTokens'] = self.config.max_tokens

        # Build request payload
        payload = {
            'contents': contents,
            'generationConfig': generation_config,
            'safetySettings': safety_settings or self.DEFAULT_SAFETY_SETTINGS
        }

        # Add system instruction if present
        if message_data['system_instruction']:
            payload['systemInstruction'] = {
                'parts': [{'text': message_data['system_instruction']}]
            }

        # Make API call (with retry logic from base class)
        endpoint = f"models/{model}:generateContent"

        def _call():
            return self._make_api_call(endpoint, payload)

        response = self._retry_with_backoff(_call)

        # Parse and return
        return self._parse_provider_response(response, model)

    def test_connection(self) -> tuple[bool, str]:
        """Test connection with a lightweight API call"""
        try:
            test_message = Message(
                role=MessageRole.USER,
                content="Hello"
            )
            response = self.complete([test_message], max_tokens=5)
            return True, f"Successfully connected to Gemini. Model: {response.model}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


def main():
    """CLI interface for testing Gemini provider"""
    import argparse
    from lib.llm_config import LLMConfigManager

    parser = argparse.ArgumentParser(description='Test Gemini provider')
    parser.add_argument('command', choices=['test', 'complete', 'vision'],
                        help='Command to run')
    parser.add_argument('--prompt', type=str, default='Hello, how are you?',
                        help='Prompt to send')
    parser.add_argument('--model', type=str, default=None,
                        help='Model to use')
    parser.add_argument('--image', type=str, default=None,
                        help='Image file path for vision test')
    parser.add_argument('--grounding', action='store_true',
                        help='Enable Google Search grounding')

    args = parser.parse_args()

    # Load config
    config_manager = LLMConfigManager()
    gemini_config = config_manager.get_provider('gemini')

    if not gemini_config:
        print("Error: Gemini provider not configured")
        sys.exit(1)

    # Create provider
    provider = GeminiProvider(gemini_config)

    if args.command == 'test':
        print(f"Testing connection to Gemini ({gemini_config.default_model})...")
        success, message = provider.test_connection()
        if success:
            print(f"✓ {message}")
            sys.exit(0)
        else:
            print(f"✗ {message}")
            sys.exit(1)

    elif args.command == 'complete':
        print(f"Sending prompt to {args.model or gemini_config.default_model}...")
        message = Message(role=MessageRole.USER, content=args.prompt)
        response = provider.complete([message], model=args.model, enable_grounding=args.grounding)

        print(f"\nResponse: {response.content}")
        print(f"\nUsage:")
        print(f"  Input tokens: {response.usage.input_tokens}")
        print(f"  Output tokens: {response.usage.output_tokens}")
        print(f"  Cost: ${response.cost:.6f}")

    elif args.command == 'vision':
        if not args.image:
            print("Error: --image required for vision command")
            sys.exit(1)

        print(f"Sending vision request to {args.model or gemini_config.default_model}...")
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
