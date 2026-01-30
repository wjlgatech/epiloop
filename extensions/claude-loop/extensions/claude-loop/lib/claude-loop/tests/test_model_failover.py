#!/usr/bin/env python3
"""
Tests for Model Failover System

Tests the automatic failover and retry logic with different providers,
API keys, and error types.
"""

import pytest
import time
from unittest.mock import Mock, patch
import sys
import os

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from model_failover import (
    ModelFailover,
    ProviderConfig,
    Provider,
    ErrorType,
    FailoverAttempt
)


class TestErrorClassification:
    """Test error classification logic."""

    def test_rate_limit_by_status_code(self):
        """429 status code should be classified as RATE_LIMIT."""
        failover = ModelFailover()
        error = Exception("Too many requests")
        error_type = failover.classify_error(error, status_code=429)
        assert error_type == ErrorType.RATE_LIMIT

    def test_rate_limit_by_message(self):
        """'rate limit' in message should be RATE_LIMIT."""
        failover = ModelFailover()
        error = Exception("Rate limit exceeded, please try again")
        error_type = failover.classify_error(error)
        assert error_type == ErrorType.RATE_LIMIT

    def test_authentication_by_status_code(self):
        """401/403 should be classified as AUTHENTICATION."""
        failover = ModelFailover()

        error = Exception("Unauthorized")
        assert failover.classify_error(error, status_code=401) == ErrorType.AUTHENTICATION
        assert failover.classify_error(error, status_code=403) == ErrorType.AUTHENTICATION

    def test_authentication_by_message(self):
        """Authentication keywords should be AUTHENTICATION."""
        failover = ModelFailover()

        assert failover.classify_error(Exception("Invalid API key")) == ErrorType.AUTHENTICATION
        assert failover.classify_error(Exception("Unauthorized access")) == ErrorType.AUTHENTICATION

    def test_server_error_classification(self):
        """500-level errors should be SERVER_ERROR."""
        failover = ModelFailover()

        for code in [500, 502, 503, 504]:
            error = Exception("Server error")
            assert failover.classify_error(error, status_code=code) == ErrorType.SERVER_ERROR

    def test_timeout_classification(self):
        """Timeout errors should be TIMEOUT."""
        failover = ModelFailover()

        assert failover.classify_error(Exception("Request timed out")) == ErrorType.TIMEOUT
        assert failover.classify_error(Exception("Connection timeout")) == ErrorType.TIMEOUT

    def test_context_length_classification(self):
        """Context length errors should be CONTEXT_LENGTH."""
        failover = ModelFailover()

        assert failover.classify_error(Exception("Context length exceeded")) == ErrorType.CONTEXT_LENGTH
        assert failover.classify_error(Exception("Too many tokens in request")) == ErrorType.CONTEXT_LENGTH

    def test_overloaded_classification(self):
        """Overloaded errors should be OVERLOADED."""
        failover = ModelFailover()

        error = Exception("Service overloaded")
        assert failover.classify_error(error, status_code=529) == ErrorType.OVERLOADED
        assert failover.classify_error(Exception("Overloaded, try again")) == ErrorType.OVERLOADED

    def test_unknown_classification(self):
        """Unrecognized errors should be UNKNOWN."""
        failover = ModelFailover()

        error = Exception("Something went wrong")
        assert failover.classify_error(error) == ErrorType.UNKNOWN


class TestRetryDecisions:
    """Test retry, rotation, and switching decisions."""

    def test_should_retry_on_transient_errors(self):
        """Transient errors should trigger retry."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider])

        # Rate limits should retry
        assert failover.should_retry(ErrorType.RATE_LIMIT, provider)

        # Timeouts should retry
        assert failover.should_retry(ErrorType.TIMEOUT, provider)

        # Server errors should retry
        assert failover.should_retry(ErrorType.SERVER_ERROR, provider)

    def test_should_not_retry_on_fatal_errors(self):
        """Fatal errors should not retry."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider])

        # Authentication errors are fatal
        assert not failover.should_retry(ErrorType.AUTHENTICATION, provider)

        # Context length errors are fatal (need different approach)
        assert not failover.should_retry(ErrorType.CONTEXT_LENGTH, provider)

    def test_should_not_retry_after_max_attempts(self):
        """Should stop retrying after max attempts."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider], max_total_attempts=3)

        # Exhaust attempts
        for i in range(3):
            failover.attempts.append(FailoverAttempt(
                provider=Provider.ANTHROPIC,
                model="claude-3-5-sonnet-20241022",
                api_key_index=0,
                attempt_number=i+1,
                error_type=ErrorType.RATE_LIMIT,
                error_message="Rate limit"
            ))

        # Should not retry after max attempts
        assert not failover.should_retry(ErrorType.RATE_LIMIT, provider)

    def test_should_rotate_key_on_rate_limit(self):
        """Should rotate API key on rate limit."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"])
        failover = ModelFailover(providers=[provider])

        # Should rotate when multiple keys available
        assert failover.should_rotate_key(ErrorType.RATE_LIMIT, provider)

        # Rotate to second key
        failover.rotate_api_key()

        # Should not rotate when on last key
        assert not failover.should_rotate_key(ErrorType.RATE_LIMIT, provider)

    def test_should_switch_provider_on_auth_error(self):
        """Should switch provider on authentication error."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
            ProviderConfig(Provider.OPENAI, api_keys=["key2"])
        ]
        failover = ModelFailover(providers=providers)

        # Should switch on auth errors
        assert failover.should_switch_provider(ErrorType.AUTHENTICATION)

    def test_should_not_switch_when_no_more_providers(self):
        """Should not switch when all providers exhausted."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider])

        # Only one provider, can't switch
        assert not failover.should_switch_provider(ErrorType.AUTHENTICATION)


class TestBackoffCalculation:
    """Test exponential backoff calculations."""

    def test_exponential_backoff(self):
        """Backoff should increase exponentially."""
        failover = ModelFailover(backoff_base=1.0)

        assert failover.get_backoff_delay(1) == 1.0  # 2^0
        assert failover.get_backoff_delay(2) == 2.0  # 2^1
        assert failover.get_backoff_delay(3) == 4.0  # 2^2
        assert failover.get_backoff_delay(4) == 8.0  # 2^3

    def test_backoff_max_cap(self):
        """Backoff should not exceed maximum."""
        failover = ModelFailover(backoff_base=1.0, backoff_max=10.0)

        # Should cap at max
        assert failover.get_backoff_delay(10) == 10.0  # Would be 512, capped at 10
        assert failover.get_backoff_delay(20) == 10.0

    def test_custom_backoff_base(self):
        """Should support custom backoff base."""
        failover = ModelFailover(backoff_base=2.0)

        assert failover.get_backoff_delay(1) == 2.0  # 2^0 * 2
        assert failover.get_backoff_delay(2) == 4.0  # 2^1 * 2
        assert failover.get_backoff_delay(3) == 8.0  # 2^2 * 2


class TestProviderConfiguration:
    """Test provider configuration and defaults."""

    def test_default_models_anthropic(self):
        """Anthropic should have default models."""
        provider = ProviderConfig(Provider.ANTHROPIC)
        assert "claude-3-5-sonnet-20241022" in provider.models
        assert "claude-3-5-haiku-20241022" in provider.models

    def test_default_models_openai(self):
        """OpenAI should have default models."""
        provider = ProviderConfig(Provider.OPENAI)
        assert "gpt-4o" in provider.models
        assert "gpt-4o-mini" in provider.models

    def test_custom_models(self):
        """Should support custom model list."""
        provider = ProviderConfig(Provider.ANTHROPIC, models=["custom-model"])
        assert provider.models == ["custom-model"]

    def test_api_key_from_environment(self):
        """Should load API key from environment."""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = ProviderConfig(Provider.ANTHROPIC)
            assert "test-key" in provider.api_keys

    def test_explicit_api_keys(self):
        """Explicit API keys should override environment."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"])
        assert provider.api_keys == ["key1", "key2"]


class TestFailoverExecution:
    """Test full failover execution flow."""

    def test_success_on_first_attempt(self):
        """Should succeed on first attempt if call works."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider])

        def successful_call(api_key, model, provider_config):
            return "success"

        result = failover.execute_with_failover(successful_call)
        assert result == "success"
        assert len(failover.attempts) == 0  # No failures

    def test_retry_on_transient_error(self):
        """Should retry on transient errors."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"])
        failover = ModelFailover(providers=[provider], backoff_base=0.01)  # Fast backoff for testing

        call_count = {'count': 0}

        def flaky_call(api_key, model, provider_config):
            call_count['count'] += 1
            if call_count['count'] < 3:
                error = Exception("Server error (500)")
                error.status_code = 500
                raise error
            return "success"

        result = failover.execute_with_failover(flaky_call)
        assert result == "success"
        assert call_count['count'] == 3
        assert len(failover.attempts) == 2  # Two failures before success

    def test_rotate_api_key_on_rate_limit(self):
        """Should rotate API key on rate limit."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"])
        failover = ModelFailover(providers=[provider], backoff_base=0.01)

        call_count = {'count': 0}
        used_keys = []

        def rate_limited_call(api_key, model, provider_config):
            call_count['count'] += 1
            used_keys.append(api_key)

            if call_count['count'] < 2:
                error = Exception("Rate limit exceeded")
                error.status_code = 429
                raise error
            return "success"

        result = failover.execute_with_failover(rate_limited_call)
        assert result == "success"
        assert len(used_keys) == 2
        assert used_keys[0] == "key1"
        assert used_keys[1] == "key2"  # Rotated to second key

    def test_switch_provider_on_persistent_failure(self):
        """Should switch provider after exhausting one provider."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
            ProviderConfig(Provider.OPENAI, api_keys=["key2"])
        ]
        failover = ModelFailover(providers=providers, backoff_base=0.01)

        call_count = {'count': 0}
        used_providers = []

        def provider_failing_call(api_key, model, provider_config):
            call_count['count'] += 1
            used_providers.append(provider_config.provider)

            if call_count['count'] < 2:
                error = Exception("Service overloaded")
                error.status_code = 529
                raise error
            return "success"

        result = failover.execute_with_failover(provider_failing_call)
        assert result == "success"
        assert Provider.ANTHROPIC in used_providers
        assert Provider.OPENAI in used_providers

    def test_all_providers_fail(self):
        """Should raise error when all providers fail."""
        providers = [
            ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
            ProviderConfig(Provider.OPENAI, api_keys=["key2"])
        ]
        failover = ModelFailover(providers=providers, max_total_attempts=3, backoff_base=0.01)

        def always_fail(api_key, model, provider_config):
            error = Exception("Server error")
            error.status_code = 500
            raise error

        with pytest.raises(RuntimeError, match="All failover attempts failed"):
            failover.execute_with_failover(always_fail)

        assert len(failover.attempts) >= 2  # Should have tried multiple times

    def test_fatal_error_stops_immediately(self):
        """Fatal errors should stop retry immediately."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"])
        failover = ModelFailover(providers=[provider])

        def auth_error_call(api_key, model, provider_config):
            error = Exception("Invalid API key")
            error.status_code = 401
            raise error

        with pytest.raises(RuntimeError):
            failover.execute_with_failover(auth_error_call)

        # Should have tried key rotation (auth error triggers key rotation)
        assert len(failover.attempts) >= 1

    def test_reset_state(self):
        """Reset should clear all state."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1", "key2"])
        failover = ModelFailover(providers=[provider])

        # Make some attempts
        failover._current_provider_index = 1
        failover._current_api_key_index = 1
        failover.attempts.append(FailoverAttempt(
            provider=Provider.ANTHROPIC,
            model="test",
            api_key_index=0,
            attempt_number=1,
            error_type=ErrorType.RATE_LIMIT,
            error_message="test"
        ))

        # Reset
        failover.reset()

        assert failover._current_provider_index == 0
        assert failover._current_api_key_index == 0
        assert len(failover.attempts) == 0


class TestConfiguration:
    """Test configuration loading."""

    def test_get_current_config(self):
        """Should return current provider, key, and model."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"], models=["model1"])
        failover = ModelFailover(providers=[provider])

        config, api_key, model = failover.get_current_config()

        assert config.provider == Provider.ANTHROPIC
        assert api_key == "key1"
        assert model == "model1"

    def test_no_api_keys_raises_error(self):
        """Should raise error if no API keys configured."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=[])
        failover = ModelFailover(providers=[provider])

        with pytest.raises(RuntimeError, match="No API keys configured"):
            failover.get_current_config()

    def test_empty_models_gets_defaults(self):
        """Empty models list should be filled with defaults."""
        provider = ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"], models=[])
        failover = ModelFailover(providers=[provider])

        # Should use defaults instead of raising error
        config, api_key, model = failover.get_current_config()
        assert model in ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
