#!/usr/bin/env python3
"""
Model Failover and API Key Rotation

Automatically retries failed API calls with different models and API keys,
providing resilience against rate limits, provider outages, and quota exhaustion.

Inspired by clawdbot's multi-provider fallback system.
"""

import os
import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of API errors for failover decisions."""
    RATE_LIMIT = "rate_limit"  # 429, rate limit exceeded
    TIMEOUT = "timeout"  # Request timeout
    AUTHENTICATION = "authentication"  # 401, 403, invalid API key
    SERVER_ERROR = "server_error"  # 500, 502, 503, 504
    CONTEXT_LENGTH = "context_length"  # Context window exceeded
    OVERLOADED = "overloaded"  # 529, provider overloaded
    UNKNOWN = "unknown"  # Other errors


class Provider(Enum):
    """Supported API providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"


@dataclass
class ProviderConfig:
    """Configuration for a provider with API keys and models."""
    provider: Provider
    api_keys: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    base_url: Optional[str] = None
    max_retries: int = 3
    timeout: int = 60

    def __post_init__(self):
        """Validate and set defaults."""
        if not self.api_keys:
            # Try to load from environment
            env_key = f"{self.provider.value.upper()}_API_KEY"
            api_key = os.getenv(env_key)
            if api_key:
                self.api_keys = [api_key]

        # Set default models if not provided
        if not self.models:
            self.models = self._get_default_models()

    def _get_default_models(self) -> List[str]:
        """Get default models for each provider."""
        defaults = {
            Provider.ANTHROPIC: ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            Provider.OPENAI: ["gpt-4o", "gpt-4o-mini"],
            Provider.GOOGLE: ["gemini-2.0-flash-exp", "gemini-1.5-pro"],
            Provider.DEEPSEEK: ["deepseek-chat", "deepseek-coder"],
        }
        return defaults.get(self.provider, [])


@dataclass
class FailoverAttempt:
    """Record of a failover attempt."""
    provider: Provider
    model: str
    api_key_index: int
    attempt_number: int
    error_type: ErrorType
    error_message: str
    timestamp: float = field(default_factory=time.time)


class ModelFailover:
    """
    Manages model failover and API key rotation with exponential backoff.

    Supports automatic fallback through multiple providers:
    anthropic → openai → google → deepseek
    """

    def __init__(self,
                 providers: Optional[List[ProviderConfig]] = None,
                 max_total_attempts: int = 12,
                 backoff_base: float = 1.0,
                 backoff_max: float = 60.0):
        """
        Initialize the failover system.

        Args:
            providers: List of provider configurations (default: anthropic only)
            max_total_attempts: Maximum attempts across all providers
            backoff_base: Base delay in seconds for exponential backoff
            backoff_max: Maximum delay in seconds
        """
        self.providers = providers or [ProviderConfig(Provider.ANTHROPIC)]
        self.max_total_attempts = max_total_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.attempts: List[FailoverAttempt] = []
        self._current_provider_index = 0
        self._current_api_key_index = 0

    def classify_error(self, error: Exception, status_code: Optional[int] = None) -> ErrorType:
        """
        Classify an error to determine failover strategy.

        Args:
            error: The exception that occurred
            status_code: HTTP status code if available

        Returns:
            ErrorType classification
        """
        error_str = str(error).lower()

        # Check status code first
        if status_code:
            if status_code == 429:
                return ErrorType.RATE_LIMIT
            elif status_code in (401, 403):
                return ErrorType.AUTHENTICATION
            elif status_code == 529:
                return ErrorType.OVERLOADED
            elif status_code in (500, 502, 503, 504):
                return ErrorType.SERVER_ERROR

        # Check error message
        if "rate limit" in error_str or "429" in error_str:
            return ErrorType.RATE_LIMIT
        elif "timeout" in error_str or "timed out" in error_str:
            return ErrorType.TIMEOUT
        elif "unauthorized" in error_str or "forbidden" in error_str or "invalid api key" in error_str:
            return ErrorType.AUTHENTICATION
        elif "context length" in error_str or "too many tokens" in error_str:
            return ErrorType.CONTEXT_LENGTH
        elif "overloaded" in error_str or "capacity" in error_str:
            return ErrorType.OVERLOADED
        elif "server error" in error_str or "internal error" in error_str:
            return ErrorType.SERVER_ERROR

        return ErrorType.UNKNOWN

    def should_retry(self, error_type: ErrorType, provider_config: ProviderConfig) -> bool:
        """
        Determine if we should retry for this error type.

        Args:
            error_type: Type of error that occurred
            provider_config: Current provider configuration

        Returns:
            True if should retry with current provider/key
        """
        # Don't retry authentication errors with same key
        if error_type == ErrorType.AUTHENTICATION:
            return False

        # Don't retry context length errors (need different approach)
        if error_type == ErrorType.CONTEXT_LENGTH:
            return False

        # Retry other errors with backoff
        return len(self.attempts) < self.max_total_attempts

    def should_rotate_key(self, error_type: ErrorType, provider_config: ProviderConfig) -> bool:
        """
        Determine if we should rotate to next API key.

        Args:
            error_type: Type of error that occurred
            provider_config: Current provider configuration

        Returns:
            True if should try next API key for same provider
        """
        # Rotate on rate limits and authentication errors
        if error_type in (ErrorType.RATE_LIMIT, ErrorType.AUTHENTICATION):
            return self._current_api_key_index + 1 < len(provider_config.api_keys)

        return False

    def should_switch_provider(self, error_type: ErrorType) -> bool:
        """
        Determine if we should switch to next provider.

        Args:
            error_type: Type of error that occurred

        Returns:
            True if should try next provider
        """
        # Switch providers on persistent failures
        if error_type in (ErrorType.AUTHENTICATION, ErrorType.OVERLOADED, ErrorType.SERVER_ERROR):
            return self._current_provider_index + 1 < len(self.providers)

        # Switch if we've exhausted API keys for current provider
        current_provider = self.providers[self._current_provider_index]
        if self._current_api_key_index >= len(current_provider.api_keys):
            return self._current_provider_index + 1 < len(self.providers)

        return False

    def get_backoff_delay(self, attempt_number: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt_number: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.backoff_base * (2 ** (attempt_number - 1))
        return min(delay, self.backoff_max)

    def rotate_api_key(self):
        """Rotate to next API key for current provider."""
        current_provider = self.providers[self._current_provider_index]
        self._current_api_key_index = (self._current_api_key_index + 1) % len(current_provider.api_keys)
        logger.info(f"Rotated to API key {self._current_api_key_index + 1}/{len(current_provider.api_keys)}")

    def switch_provider(self):
        """Switch to next provider in chain."""
        self._current_provider_index += 1
        self._current_api_key_index = 0  # Reset key index for new provider

        if self._current_provider_index < len(self.providers):
            new_provider = self.providers[self._current_provider_index]
            logger.info(f"Switched to provider: {new_provider.provider.value}")
        else:
            logger.error("All providers exhausted")

    def get_current_config(self) -> Tuple[ProviderConfig, str, str]:
        """
        Get current provider configuration, API key, and model.

        Returns:
            Tuple of (provider_config, api_key, model)
        """
        if self._current_provider_index >= len(self.providers):
            raise RuntimeError("All providers exhausted")

        provider_config = self.providers[self._current_provider_index]

        if not provider_config.api_keys:
            raise RuntimeError(f"No API keys configured for {provider_config.provider.value}")

        if not provider_config.models:
            raise RuntimeError(f"No models configured for {provider_config.provider.value}")

        api_key = provider_config.api_keys[self._current_api_key_index]
        model = provider_config.models[0]  # Use first model by default

        return provider_config, api_key, model

    def execute_with_failover(self,
                              api_call: Callable[[str, str, ProviderConfig], Any],
                              *args, **kwargs) -> Any:
        """
        Execute an API call with automatic failover and retry.

        Args:
            api_call: Function that makes the API call (api_key, model, provider_config) -> result
            *args: Additional positional arguments for api_call
            **kwargs: Additional keyword arguments for api_call

        Returns:
            Result from successful API call

        Raises:
            RuntimeError: If all failover attempts fail
        """
        attempt = 0
        last_error = None

        while attempt < self.max_total_attempts:
            attempt += 1

            try:
                # Get current configuration
                provider_config, api_key, model = self.get_current_config()

                logger.info(f"Attempt {attempt}: {provider_config.provider.value}/{model} (key {self._current_api_key_index + 1})")

                # Make API call
                result = api_call(api_key, model, provider_config, *args, **kwargs)

                # Success!
                logger.info(f"Success on attempt {attempt}")
                return result

            except Exception as e:
                last_error = e

                # Classify error
                status_code = getattr(e, 'status_code', None)
                error_type = self.classify_error(e, status_code)

                # Record attempt
                provider_config, _, model = self.get_current_config()
                self.attempts.append(FailoverAttempt(
                    provider=provider_config.provider,
                    model=model,
                    api_key_index=self._current_api_key_index,
                    attempt_number=attempt,
                    error_type=error_type,
                    error_message=str(e)
                ))

                logger.warning(f"Attempt {attempt} failed: {error_type.value} - {str(e)[:100]}")

                # Decide on failover strategy
                if self.should_rotate_key(error_type, provider_config):
                    self.rotate_api_key()
                elif self.should_switch_provider(error_type):
                    self.switch_provider()
                elif not self.should_retry(error_type, provider_config):
                    # Fatal error, stop retrying
                    logger.error(f"Fatal error, stopping: {error_type.value}")
                    break

                # Backoff before retry
                if attempt < self.max_total_attempts:
                    delay = self.get_backoff_delay(attempt)
                    logger.info(f"Backing off for {delay:.1f}s")
                    time.sleep(delay)

        # All attempts failed
        logger.error(f"All {attempt} attempts failed")
        self.log_failure_summary()
        raise RuntimeError(f"All failover attempts failed. Last error: {last_error}")

    def log_failure_summary(self):
        """Log a summary of all failure attempts."""
        if not self.attempts:
            return

        logger.error("=== Failover Attempt Summary ===")
        for attempt in self.attempts:
            logger.error(
                f"  #{attempt.attempt_number}: {attempt.provider.value}/{attempt.model} "
                f"(key {attempt.api_key_index + 1}) - {attempt.error_type.value}"
            )

    def reset(self):
        """Reset failover state to start from beginning."""
        self._current_provider_index = 0
        self._current_api_key_index = 0
        self.attempts.clear()


def load_config_from_yaml(config_path: str) -> List[ProviderConfig]:
    """
    Load provider configuration from YAML file.

    Args:
        config_path: Path to config.yaml

    Returns:
        List of ProviderConfig objects
    """
    import yaml

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    providers = []
    failover_config = config.get('failover', {})

    for provider_data in failover_config.get('providers', []):
        provider = Provider(provider_data['name'])
        providers.append(ProviderConfig(
            provider=provider,
            api_keys=provider_data.get('api_keys', []),
            models=provider_data.get('models', []),
            base_url=provider_data.get('base_url'),
            max_retries=provider_data.get('max_retries', 3),
            timeout=provider_data.get('timeout', 60)
        ))

    return providers


# Example usage and testing
if __name__ == "__main__":
    # Example: Simulated API call that fails
    def mock_api_call(api_key: str, model: str, provider_config: ProviderConfig,
                     fail_count: dict = None) -> str:
        """Mock API call for testing."""
        if fail_count is None:
            fail_count = {'count': 0}

        fail_count['count'] += 1

        # Simulate failures
        if fail_count['count'] == 1:
            raise Exception("Rate limit exceeded (429)")
        elif fail_count['count'] == 2:
            raise Exception("Server overloaded (529)")
        else:
            return f"Success with {provider_config.provider.value}/{model}"

    # Configure multiple providers
    providers = [
        ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"]),
        ProviderConfig(Provider.OPENAI, api_keys=["key3"]),
    ]

    # Create failover manager
    failover = ModelFailover(providers=providers)

    # Execute with failover
    try:
        fail_count = {'count': 0}
        result = failover.execute_with_failover(mock_api_call, fail_count=fail_count)
        print(f"Final result: {result}")
    except RuntimeError as e:
        print(f"Failed: {e}")
