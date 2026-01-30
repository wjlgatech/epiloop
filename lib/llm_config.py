#!/usr/bin/env python3
"""
LLM Provider Configuration Management

Unified configuration system for managing multiple LLM provider credentials and settings.
Supports both environment variables and YAML configuration files.
"""

import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
from pathlib import Path
import yaml


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider"""

    name: str  # Provider name: openai, gemini, deepseek, claude
    enabled: bool = True

    # API Configuration
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 120  # seconds
    max_tokens: int = 4096

    # Model Configuration
    default_model: Optional[str] = None
    available_models: List[str] = field(default_factory=list)

    # Cost Tracking (per 1000 tokens)
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0

    # Provider-specific settings
    extra_settings: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization"""
        # LiteLLM doesn't require API key in config (uses env vars)
        if self.enabled and not self.api_key and self.name != 'litellm':
            raise ValueError(f"Provider {self.name} is enabled but has no API key")

        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout}")

        if self.max_tokens <= 0:
            raise ValueError(f"Max tokens must be positive, got {self.max_tokens}")

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProviderConfig':
        """Create from dictionary"""
        return cls(**data)


class LLMConfigManager:
    """Manager for LLM provider configurations"""

    # Default configuration file path
    DEFAULT_CONFIG_PATH = Path.home() / ".claude-loop" / "providers.yaml"

    # Environment variable mappings
    ENV_VAR_MAP = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "litellm": "LITELLM_API_KEY"  # LiteLLM uses env vars for each provider
    }

    # Default provider configurations
    DEFAULT_CONFIGS = {
        "openai": {
            "name": "openai",
            "enabled": False,
            "base_url": "https://api.openai.com/v1",
            "timeout": 120,
            "max_tokens": 4096,
            "default_model": "gpt-4o",
            "available_models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
            "input_cost_per_1k": 2.50,  # gpt-4o pricing
            "output_cost_per_1k": 10.00,
            "extra_settings": {}
        },
        "gemini": {
            "name": "gemini",
            "enabled": False,
            "base_url": "https://generativelanguage.googleapis.com/v1",
            "timeout": 120,
            "max_tokens": 8192,
            "default_model": "gemini-2.0-flash",
            "available_models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-2.0-flash-thinking"],
            "input_cost_per_1k": 0.10,  # gemini-2.0-flash pricing
            "output_cost_per_1k": 0.40,
            "extra_settings": {
                "safety_settings": "default"
            }
        },
        "deepseek": {
            "name": "deepseek",
            "enabled": False,
            "base_url": "https://api.deepseek.com/v1",
            "timeout": 120,
            "max_tokens": 4096,
            "default_model": "deepseek-chat",
            "available_models": ["deepseek-chat", "deepseek-reasoner"],
            "input_cost_per_1k": 0.14,  # deepseek-v3 pricing
            "output_cost_per_1k": 0.28,
            "extra_settings": {}
        },
        "claude": {
            "name": "claude",
            "enabled": True,
            "base_url": "https://api.anthropic.com/v1",
            "timeout": 120,
            "max_tokens": 4096,
            "default_model": "claude-sonnet-4",
            "available_models": ["claude-opus-4", "claude-sonnet-4", "claude-haiku-4"],
            "input_cost_per_1k": 3.00,  # claude-sonnet-4 pricing
            "output_cost_per_1k": 15.00,
            "extra_settings": {}
        },
        "litellm": {
            "name": "litellm",
            "enabled": False,  # Disabled by default (feature flag controlled)
            "base_url": None,  # LiteLLM handles endpoints
            "timeout": 120,
            "max_tokens": 4096,
            "default_model": "gpt-4o-mini",  # Cheap, reliable default
            "available_models": [],  # Auto-detected from litellm
            "input_cost_per_1k": 0.15,  # gpt-4o-mini pricing (fallback)
            "output_cost_per_1k": 0.60,
            "extra_settings": {
                "fallback_models": ["gpt-4o", "claude-sonnet-4-5"],
                "auto_detect_models": True
            }
        }
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to configuration file (default: ~/.claude-loop/providers.yaml)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.providers: Dict[str, ProviderConfig] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment variables"""
        # Start with defaults
        configs = {}

        # Load from file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_configs = yaml.safe_load(f) or {}
                    configs = file_configs.get('providers', {})
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}", file=sys.stderr)

        # Apply defaults for any missing providers
        for provider_name, default_config in self.DEFAULT_CONFIGS.items():
            if provider_name not in configs:
                configs[provider_name] = default_config.copy()
            else:
                # Merge with defaults (file config takes precedence)
                merged = default_config.copy()
                merged.update(configs[provider_name])
                configs[provider_name] = merged

        # Override with environment variables
        for provider_name, env_var in self.ENV_VAR_MAP.items():
            api_key = os.getenv(env_var)
            if api_key:
                if provider_name not in configs:
                    configs[provider_name] = self.DEFAULT_CONFIGS[provider_name].copy()
                configs[provider_name]['api_key'] = api_key
                configs[provider_name]['enabled'] = True

        # Create ProviderConfig objects
        for provider_name, config_dict in configs.items():
            try:
                # If no API key is set and provider is enabled by default, disable it
                if not config_dict.get('api_key') or config_dict.get('api_key') == 'disabled':
                    config_dict['enabled'] = False
                    config_dict['api_key'] = 'disabled'

                self.providers[provider_name] = ProviderConfig.from_dict(config_dict)
            except Exception as e:
                print(f"Warning: Failed to load config for {provider_name}: {e}", file=sys.stderr)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get configuration for a specific provider"""
        return self.providers.get(name)

    def list_providers(self, enabled_only: bool = False) -> List[ProviderConfig]:
        """
        List all configured providers

        Args:
            enabled_only: If True, only return enabled providers

        Returns:
            List of ProviderConfig objects
        """
        providers = list(self.providers.values())
        if enabled_only:
            providers = [p for p in providers if p.enabled]
        return providers

    def save_config(self):
        """Save current configuration to file"""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary format
        config_dict = {
            'providers': {
                name: provider.to_dict()
                for name, provider in self.providers.items()
            }
        }

        # Write to file
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

    def test_provider(self, name: str) -> tuple[bool, str]:
        """
        Test provider connectivity with a lightweight call

        Args:
            name: Provider name

        Returns:
            Tuple of (success: bool, message: str)
        """
        provider = self.get_provider(name)
        if not provider:
            return False, f"Provider {name} not found"

        if not provider.enabled:
            return False, f"Provider {name} is disabled"

        if not provider.api_key or provider.api_key == 'disabled':
            return False, f"Provider {name} has no API key configured"

        # TODO: Implement actual API test calls in LLM-002 (Provider Abstraction Layer)
        # For now, just validate configuration
        try:
            # Basic validation
            if not provider.base_url:
                return False, f"Provider {name} has no base URL configured"

            return True, f"Provider {name} configuration is valid (API test not yet implemented)"
        except Exception as e:
            return False, f"Provider {name} configuration error: {str(e)}"


def main():
    """CLI interface for llm-config"""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Provider Configuration Manager")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # list command
    list_parser = subparsers.add_parser('list', help='List all providers')
    list_parser.add_argument('--enabled-only', action='store_true', help='Show only enabled providers')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # test command
    test_parser = subparsers.add_parser('test', help='Test provider connectivity')
    test_parser.add_argument('provider', help='Provider name to test')

    # show command
    show_parser = subparsers.add_parser('show', help='Show provider configuration')
    show_parser.add_argument('provider', help='Provider name to show')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize manager
    manager = LLMConfigManager()

    if args.command == 'list':
        providers = manager.list_providers(enabled_only=args.enabled_only)

        if args.json:
            import json
            output = [p.to_dict() for p in providers]
            print(json.dumps(output, indent=2))
        else:
            print(f"\n{'Provider':<15} {'Enabled':<10} {'Model':<30} {'API Key':<15}")
            print("-" * 75)
            for p in providers:
                api_key_status = "Set" if p.api_key and p.api_key != 'disabled' else "Not set"
                print(f"{p.name:<15} {'Yes' if p.enabled else 'No':<10} {p.default_model or 'N/A':<30} {api_key_status:<15}")
            print()

    elif args.command == 'test':
        success, message = manager.test_provider(args.provider)
        print(message)
        return 0 if success else 1

    elif args.command == 'show':
        provider = manager.get_provider(args.provider)
        if not provider:
            print(f"Provider {args.provider} not found", file=sys.stderr)
            return 1

        import json
        print(json.dumps(provider.to_dict(), indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
