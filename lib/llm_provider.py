#!/usr/bin/env python3
"""
LLM Provider Abstraction Layer

Unified interface for calling different LLM providers with standardized
message formats, responses, retry logic, and timeout handling.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
import sys

if TYPE_CHECKING:
    from lib.llm_config import ProviderConfig


class MessageRole(str, Enum):
    """Standard message roles across providers"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Standard message format"""
    role: MessageRole
    content: str

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "role": self.role.value,
            "content": self.content
        }


@dataclass
class ImageInput:
    """Image input for vision models"""
    # One of: base64, url, or file_path
    base64: Optional[str] = None
    url: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: str = "image/jpeg"

    def __post_init__(self):
        """Validate that exactly one input method is provided"""
        inputs = sum([
            self.base64 is not None,
            self.url is not None,
            self.file_path is not None
        ])
        if inputs != 1:
            raise ValueError("Exactly one of base64, url, or file_path must be provided")


@dataclass
class TokenUsage:
    """Token usage statistics"""
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    model: str
    usage: TokenUsage
    cost: float  # Cost in USD
    provider: str
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage.to_dict(),
            "cost": self.cost,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
            "raw_response": self.raw_response
        }


class ProviderError(Exception):
    """Base exception for provider errors"""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded"""
    pass


class TimeoutError(ProviderError):
    """Request timeout"""
    pass


class AuthenticationError(ProviderError):
    """Authentication failed"""
    pass


class InvalidRequestError(ProviderError):
    """Invalid request parameters"""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, config: 'ProviderConfig'):
        """
        Initialize provider with configuration

        Args:
            config: ProviderConfig object from llm_config.py
        """
        self.config = config
        self.provider_name = config.name

    @abstractmethod
    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Complete a chat conversation

        Args:
            messages: List of Message objects
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse object with standardized format

        Raises:
            ProviderError: On provider-specific errors
            RateLimitError: On rate limit errors
            TimeoutError: On timeout
            AuthenticationError: On auth errors
            InvalidRequestError: On invalid parameters
        """
        pass

    @abstractmethod
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
        Complete with vision capabilities (VLM)

        Args:
            messages: List of Message objects
            images: List of ImageInput objects
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse object with standardized format

        Raises:
            ProviderError: On provider-specific errors
            NotImplementedError: If provider doesn't support vision
        """
        pass

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost based on token usage

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1000) * self.config.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.config.output_cost_per_1k
        return input_cost + output_cost

    def _retry_with_backoff(
        self,
        func,  # callable
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0
    ) -> Any:
        """
        Retry a function with exponential backoff

        Args:
            func: Function to retry (must be a callable)
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for delay on each retry
            max_delay: Maximum delay between retries

        Returns:
            Result from successful function call

        Raises:
            Last exception if all retries fail
        """
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func()
            except RateLimitError as e:
                last_exception = e
                if attempt < max_retries:
                    print(f"Rate limit hit, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                          file=sys.stderr)
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                else:
                    raise
            except TimeoutError as e:
                last_exception = e
                if attempt < max_retries:
                    print(f"Timeout, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                          file=sys.stderr)
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                else:
                    raise
            except (AuthenticationError, InvalidRequestError):
                # Don't retry authentication or invalid request errors
                raise

        # This shouldn't be reached, but just in case
        if last_exception:
            raise last_exception

    def _with_timeout(
        self,
        func,  # callable
        timeout: Optional[int] = None
    ) -> Any:
        """
        Execute function with timeout

        Args:
            func: Function to execute
            timeout: Timeout in seconds (uses config default if not specified)

        Returns:
            Result from function

        Raises:
            TimeoutError: If function exceeds timeout
        """
        timeout = timeout or self.config.timeout

        # For synchronous functions, we use a simple approach
        # In production, consider using concurrent.futures or signal
        import signal

        def timeout_handler(_signum, _frame):
            raise TimeoutError(f"Request exceeded timeout of {timeout}s")

        # Set the signal alarm
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            result = func()
            signal.alarm(0)  # Disable alarm
            return result
        except TimeoutError:
            raise
        finally:
            signal.signal(signal.SIGALRM, old_handler)

    def test_connection(self) -> tuple[bool, str]:
        """
        Test provider connectivity with a minimal request

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            messages = [Message(role=MessageRole.USER, content="Hi")]
            response = self.complete(
                messages=messages,
                max_tokens=10
            )
            return True, f"Successfully connected to {self.provider_name}. Model: {response.model}"
        except Exception as e:
            return False, f"Failed to connect to {self.provider_name}: {str(e)}"

    @abstractmethod
    def _convert_messages_to_provider_format(
        self,
        messages: List[Message]
    ) -> Any:
        """
        Convert standard messages to provider-specific format

        Args:
            messages: List of standard Message objects

        Returns:
            Provider-specific message format
        """
        pass

    @abstractmethod
    def _parse_provider_response(
        self,
        response: Any,
        model: str
    ) -> LLMResponse:
        """
        Parse provider-specific response to standard format

        Args:
            response: Raw provider response
            model: Model name used

        Returns:
            Standardized LLMResponse object
        """
        pass


class ProviderFactory:
    """Factory for creating provider instances"""

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, provider_name: str, provider_class: type):
        """
        Register a provider class

        Args:
            provider_name: Name of the provider (e.g., 'openai', 'gemini')
            provider_class: Provider class (must inherit from LLMProvider)
        """
        if not issubclass(provider_class, LLMProvider):
            raise ValueError(f"Provider class must inherit from LLMProvider")
        cls._registry[provider_name] = provider_class

    @classmethod
    def create(cls, config: 'ProviderConfig') -> LLMProvider:
        """
        Create a provider instance from configuration

        Args:
            config: ProviderConfig object

        Returns:
            Provider instance

        Raises:
            ValueError: If provider is not registered
        """
        provider_class = cls._registry.get(config.name)
        if not provider_class:
            raise ValueError(
                f"Provider '{config.name}' not registered. "
                f"Available providers: {list(cls._registry.keys())}"
            )
        return provider_class(config)

    @classmethod
    def list_registered(cls) -> List[str]:
        """List all registered provider names"""
        return list(cls._registry.keys())


def main():
    """CLI interface for testing provider abstraction"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="LLM Provider Abstraction Layer")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # test command
    test_parser = subparsers.add_parser('test', help='Test provider')
    test_parser.add_argument('provider', help='Provider name')
    test_parser.add_argument('--prompt', default='Hello', help='Test prompt')
    test_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # list command
    subparsers.add_parser('list', help='List registered providers')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'list':
        providers = ProviderFactory.list_registered()
        print("Registered providers:", ", ".join(providers))
        return 0

    elif args.command == 'test':
        # Import config manager
        try:
            from lib.llm_config import LLMConfigManager
        except ImportError:
            # Try parent directory import
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from lib.llm_config import LLMConfigManager

        # Load config
        manager = LLMConfigManager()
        config = manager.get_provider(args.provider)

        if not config:
            print(f"Provider {args.provider} not found", file=sys.stderr)
            return 1

        if not config.enabled:
            print(f"Provider {args.provider} is disabled", file=sys.stderr)
            return 1

        # Create provider
        try:
            provider = ProviderFactory.create(config)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Test connection
        success, message = provider.test_connection()

        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)

        return 0 if success else 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
