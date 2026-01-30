#!/usr/bin/env python3
"""
Unit tests for LLM Provider Configuration Management
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from lib package
from lib.llm_config import ProviderConfig, LLMConfigManager


class TestProviderConfig:
    """Tests for ProviderConfig dataclass"""

    def test_create_valid_config(self):
        """Test creating a valid provider configuration"""
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o"
        )

        assert config.name == "openai"
        assert config.enabled is True
        assert config.api_key == "test-key"
        assert config.default_model == "gpt-4o"
        assert config.timeout == 120  # default
        assert config.max_tokens == 4096  # default

    def test_enabled_without_api_key_raises_error(self):
        """Test that enabled provider without API key raises error"""
        with pytest.raises(ValueError, match="has no API key"):
            ProviderConfig(
                name="openai",
                enabled=True,
                api_key=None
            )

    def test_disabled_without_api_key_succeeds(self):
        """Test that disabled provider without API key is allowed"""
        config = ProviderConfig(
            name="openai",
            enabled=False,
            api_key=None
        )
        assert config.enabled is False

    def test_negative_timeout_raises_error(self):
        """Test that negative timeout raises error"""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            ProviderConfig(
                name="openai",
                enabled=False,
                api_key="test",
                timeout=-1
            )

    def test_zero_max_tokens_raises_error(self):
        """Test that zero max_tokens raises error"""
        with pytest.raises(ValueError, match="Max tokens must be positive"):
            ProviderConfig(
                name="openai",
                enabled=False,
                api_key="test",
                max_tokens=0
            )

    def test_to_dict_conversion(self):
        """Test conversion to dictionary"""
        config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"]
        )

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict['name'] == "openai"
        assert config_dict['enabled'] is True
        assert config_dict['api_key'] == "test-key"
        assert config_dict['default_model'] == "gpt-4o"
        assert config_dict['available_models'] == ["gpt-4o", "gpt-4o-mini"]

    def test_from_dict_conversion(self):
        """Test creation from dictionary"""
        config_dict = {
            'name': 'openai',
            'enabled': True,
            'api_key': 'test-key',
            'default_model': 'gpt-4o',
            'base_url': 'https://api.openai.com/v1',
            'timeout': 60,
            'max_tokens': 2048,
            'available_models': ['gpt-4o'],
            'input_cost_per_1k': 2.5,
            'output_cost_per_1k': 10.0,
            'extra_settings': {}
        }

        config = ProviderConfig.from_dict(config_dict)

        assert config.name == "openai"
        assert config.enabled is True
        assert config.api_key == "test-key"
        assert config.timeout == 60
        assert config.max_tokens == 2048


class TestLLMConfigManager:
    """Tests for LLMConfigManager"""

    def test_initialization_with_defaults(self):
        """Test initialization loads default configurations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            # Should have all default providers
            assert len(manager.providers) == 4
            assert "openai" in manager.providers
            assert "gemini" in manager.providers
            assert "deepseek" in manager.providers
            assert "claude" in manager.providers

            # Without API keys, all providers should be disabled
            claude = manager.get_provider("claude")
            assert claude is not None
            assert claude.enabled is False  # Disabled without API key

    def test_load_from_environment_variables(self):
        """Test loading API keys from environment variables"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"

            with patch.dict(os.environ, {
                'OPENAI_API_KEY': 'test-openai-key',
                'GOOGLE_API_KEY': 'test-google-key'
            }):
                manager = LLMConfigManager(config_path=config_path)

                openai = manager.get_provider("openai")
                assert openai is not None
                assert openai.api_key == "test-openai-key"
                assert openai.enabled is True

                gemini = manager.get_provider("gemini")
                assert gemini is not None
                assert gemini.api_key == "test-google-key"
                assert gemini.enabled is True

    def test_save_and_load_config(self):
        """Test saving and loading configuration from file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"

            # Create manager and modify config
            manager1 = LLMConfigManager(config_path=config_path)
            openai = manager1.get_provider("openai")
            openai.api_key = "saved-key"
            openai.enabled = True

            # Save config
            manager1.save_config()

            # Load in new manager
            manager2 = LLMConfigManager(config_path=config_path)
            openai2 = manager2.get_provider("openai")

            assert openai2.api_key == "saved-key"
            assert openai2.enabled is True

    def test_list_providers_all(self):
        """Test listing all providers"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            providers = manager.list_providers(enabled_only=False)

            assert len(providers) >= 4
            provider_names = [p.name for p in providers]
            assert "openai" in provider_names
            assert "gemini" in provider_names
            assert "deepseek" in provider_names
            assert "claude" in provider_names

    def test_list_providers_enabled_only(self):
        """Test listing only enabled providers"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"

            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
                manager = LLMConfigManager(config_path=config_path)

                all_providers = manager.list_providers(enabled_only=False)
                enabled_providers = manager.list_providers(enabled_only=True)

                assert len(all_providers) >= len(enabled_providers)
                assert all(p.enabled for p in enabled_providers)

    def test_get_nonexistent_provider(self):
        """Test getting a provider that doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            provider = manager.get_provider("nonexistent")
            assert provider is None

    def test_test_provider_not_found(self):
        """Test testing a provider that doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            success, message = manager.test_provider("nonexistent")
            assert success is False
            assert "not found" in message

    def test_test_provider_disabled(self):
        """Test testing a disabled provider"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            success, message = manager.test_provider("openai")
            assert success is False
            assert "disabled" in message or "no API key" in message

    def test_test_provider_enabled(self):
        """Test testing an enabled provider"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"

            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
                manager = LLMConfigManager(config_path=config_path)

                success, message = manager.test_provider("openai")
                # Should succeed validation (actual API test not implemented yet)
                assert success is True

    def test_env_var_override_file_config(self):
        """Test that environment variables override file configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"

            # Create config file with one key
            import yaml
            file_config = {
                'providers': {
                    'openai': {
                        'name': 'openai',
                        'enabled': True,
                        'api_key': 'file-key',
                        'default_model': 'gpt-4o'
                    }
                }
            }
            with open(config_path, 'w') as f:
                yaml.safe_dump(file_config, f)

            # Load with different env var
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'env-key'}):
                manager = LLMConfigManager(config_path=config_path)

                openai = manager.get_provider("openai")
                # Env var should override file
                assert openai.api_key == "env-key"
                assert openai.enabled is True

    def test_default_pricing_values(self):
        """Test that default pricing values are set correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            manager = LLMConfigManager(config_path=config_path)

            # Check OpenAI pricing
            openai = manager.get_provider("openai")
            assert openai.input_cost_per_1k == 2.50
            assert openai.output_cost_per_1k == 10.00

            # Check DeepSeek pricing (should be very cheap)
            deepseek = manager.get_provider("deepseek")
            assert deepseek.input_cost_per_1k == 0.14
            assert deepseek.output_cost_per_1k == 0.28

            # Check Gemini pricing (should be cheap)
            gemini = manager.get_provider("gemini")
            assert gemini.input_cost_per_1k == 0.10
            assert gemini.output_cost_per_1k == 0.40


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
