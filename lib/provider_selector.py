#!/usr/bin/env python3
"""
Provider Selection Logic

Selects the optimal LLM provider based on task complexity, required capabilities,
and cost optimization. Implements fallback chains for reliability.

Usage:
    python3 lib/provider_selector.py select --complexity 3 --requires-vision
    python3 lib/provider_selector.py select --complexity 5 --requires-tools --preferred openai
    python3 lib/provider_selector.py fallback-chain --provider litellm/gpt-4o-mini
"""

import sys
import os
import json
import yaml
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ProviderCapabilities:
    """Provider capabilities for filtering"""
    vision: bool = False
    tools: bool = False
    json_mode: bool = False


@dataclass
class ProviderConfig:
    """Provider configuration"""
    name: str
    model: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    capabilities: ProviderCapabilities
    enabled: bool = True
    max_tokens: int = 4096
    timeout: int = 120


@dataclass
class SelectionResult:
    """Provider selection result"""
    provider: str
    model: str
    reasoning: str
    fallback_chain: List[str]
    cost_estimate: Optional[float] = None
    selection_time_ms: float = 0


class ProviderSelector:
    """
    Selects optimal provider based on complexity and capabilities.

    Complexity thresholds:
    - 0-2: cheap models (Haiku, GPT-4o-mini, Gemini Flash)
    - 3-5: medium models (Sonnet, GPT-4o, Gemini Pro)
    - 6+: powerful models (Opus, O1, Gemini Thinking)
    """

    # Default provider configurations (fallback if YAML not found)
    DEFAULT_PROVIDERS = {
        "litellm/gpt-4o-mini": {
            "name": "litellm",
            "model": "gpt-4o-mini",
            "input_cost_per_1k": 0.15,
            "output_cost_per_1k": 0.60,
            "capabilities": {"vision": True, "tools": True, "json_mode": True},
            "enabled": True
        },
        "litellm/gpt-4o": {
            "name": "litellm",
            "model": "gpt-4o",
            "input_cost_per_1k": 2.50,
            "output_cost_per_1k": 10.00,
            "capabilities": {"vision": True, "tools": True, "json_mode": True},
            "enabled": True
        },
        "claude-haiku": {
            "name": "anthropic",
            "model": "claude-3-5-haiku-20241022",
            "input_cost_per_1k": 0.25,
            "output_cost_per_1k": 1.25,
            "capabilities": {"vision": True, "tools": True, "json_mode": False},
            "enabled": True
        },
        "claude-sonnet": {
            "name": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "input_cost_per_1k": 3.00,
            "output_cost_per_1k": 15.00,
            "capabilities": {"vision": True, "tools": True, "json_mode": False},
            "enabled": True
        },
        "claude-opus": {
            "name": "anthropic",
            "model": "claude-opus-4-20250514",
            "input_cost_per_1k": 15.00,
            "output_cost_per_1k": 75.00,
            "capabilities": {"vision": True, "tools": True, "json_mode": False},
            "enabled": True
        },
        "gemini-flash": {
            "name": "google",
            "model": "gemini-2.0-flash-exp",
            "input_cost_per_1k": 0.10,
            "output_cost_per_1k": 0.40,
            "capabilities": {"vision": True, "tools": True, "json_mode": True},
            "enabled": True
        },
        "gemini-pro": {
            "name": "google",
            "model": "gemini-1.5-pro",
            "input_cost_per_1k": 1.25,
            "output_cost_per_1k": 5.00,
            "capabilities": {"vision": True, "tools": True, "json_mode": True},
            "enabled": True
        },
        "deepseek-chat": {
            "name": "deepseek",
            "model": "deepseek-chat",
            "input_cost_per_1k": 0.14,
            "output_cost_per_1k": 0.28,
            "capabilities": {"vision": False, "tools": True, "json_mode": True},
            "enabled": True
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize provider selector.

        Args:
            config_path: Path to lib/llm_providers.yaml (optional)
        """
        self.config_path = config_path or self._find_config_path()
        self.providers = self._load_providers()

    def _find_config_path(self) -> Optional[str]:
        """Find llm_providers.yaml in standard locations"""
        candidates = [
            "lib/llm_providers.yaml",
            "../lib/llm_providers.yaml",
            "/Users/jialiang.wu/Documents/Projects/claude-loop/lib/llm_providers.yaml"
        ]

        for path in candidates:
            if os.path.exists(path):
                return path

        return None

    def _load_providers(self) -> Dict[str, ProviderConfig]:
        """Load provider configurations from YAML or use defaults"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                return self._parse_yaml_config(config_data)

        # Use default configurations
        return self._parse_default_config()

    def _parse_yaml_config(self, config_data: dict) -> Dict[str, ProviderConfig]:
        """Parse YAML configuration into ProviderConfig objects"""
        providers = {}

        for provider_key, provider_data in config_data.items():
            capabilities = ProviderCapabilities(
                vision=provider_data.get('capabilities', {}).get('vision', False),
                tools=provider_data.get('capabilities', {}).get('tools', False),
                json_mode=provider_data.get('capabilities', {}).get('json_mode', False)
            )

            providers[provider_key] = ProviderConfig(
                name=provider_data.get('name'),
                model=provider_data.get('model'),
                input_cost_per_1k=provider_data.get('input_cost_per_1k'),
                output_cost_per_1k=provider_data.get('output_cost_per_1k'),
                capabilities=capabilities,
                enabled=provider_data.get('enabled', True),
                max_tokens=provider_data.get('max_tokens', 4096),
                timeout=provider_data.get('timeout', 120)
            )

        return providers

    def _parse_default_config(self) -> Dict[str, ProviderConfig]:
        """Parse default configuration into ProviderConfig objects"""
        providers = {}

        for provider_key, provider_data in self.DEFAULT_PROVIDERS.items():
            cap_data = provider_data['capabilities']
            capabilities = ProviderCapabilities(
                vision=cap_data.get('vision', False),
                tools=cap_data.get('tools', False),
                json_mode=cap_data.get('json_mode', False)
            )

            providers[provider_key] = ProviderConfig(
                name=provider_data['name'],
                model=provider_data['model'],
                input_cost_per_1k=provider_data['input_cost_per_1k'],
                output_cost_per_1k=provider_data['output_cost_per_1k'],
                capabilities=capabilities,
                enabled=provider_data.get('enabled', True)
            )

        return providers

    def select_provider(self,
                       complexity: int,
                       requires_vision: bool = False,
                       requires_tools: bool = False,
                       requires_json_mode: bool = False,
                       preferred_provider: Optional[str] = None) -> SelectionResult:
        """
        Select optimal provider based on requirements.

        Args:
            complexity: Task complexity (0-10)
            requires_vision: Whether vision capability is required
            requires_tools: Whether tool use is required
            requires_json_mode: Whether JSON mode is required
            preferred_provider: Preferred provider name (override)

        Returns:
            SelectionResult with provider, model, reasoning, fallback chain
        """
        start_time = time.time()

        # Use preferred provider if specified
        if preferred_provider:
            if preferred_provider in self.providers:
                provider = self.providers[preferred_provider]
                result = SelectionResult(
                    provider=provider.name,
                    model=provider.model,
                    reasoning=f"Preferred provider specified: {preferred_provider}",
                    fallback_chain=self._build_fallback_chain(preferred_provider),
                    selection_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                return result
            else:
                # Fall through to normal selection if preferred not found
                pass

        # Filter providers by capabilities
        candidates = self._filter_by_capabilities(
            requires_vision, requires_tools, requires_json_mode
        )

        if not candidates:
            # No providers match requirements - fallback to default
            fallback_result = SelectionResult(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                reasoning="No providers matched requirements, using default",
                fallback_chain=["claude-sonnet", "claude-opus", "claude-code-cli"],
                selection_time_ms=round((time.time() - start_time) * 1000, 2)
            )
            return fallback_result

        # Select based on complexity
        selected = self._select_by_complexity(candidates, complexity)

        # Build reasoning
        reasoning_parts = []
        reasoning_parts.append(f"Complexity: {complexity}")
        if requires_vision:
            reasoning_parts.append("vision required")
        if requires_tools:
            reasoning_parts.append("tools required")
        if requires_json_mode:
            reasoning_parts.append("JSON mode required")
        reasoning_parts.append(f"selected cheapest capable: {selected.model}")

        result = SelectionResult(
            provider=selected.name,
            model=selected.model,
            reasoning=", ".join(reasoning_parts),
            fallback_chain=self._build_fallback_chain(
                next(k for k, v in self.providers.items() if v.model == selected.model)
            ),
            cost_estimate=self._estimate_cost(selected),
            selection_time_ms=round((time.time() - start_time) * 1000, 2)
        )

        return result

    def _filter_by_capabilities(self,
                                requires_vision: bool,
                                requires_tools: bool,
                                requires_json_mode: bool) -> List[ProviderConfig]:
        """Filter providers by required capabilities"""
        candidates = []

        for provider_key, provider in self.providers.items():
            if not provider.enabled:
                continue

            # Check capabilities
            if requires_vision and not provider.capabilities.vision:
                continue
            if requires_tools and not provider.capabilities.tools:
                continue
            if requires_json_mode and not provider.capabilities.json_mode:
                continue

            candidates.append(provider)

        return candidates

    def _select_by_complexity(self,
                             candidates: List[ProviderConfig],
                             complexity: int) -> ProviderConfig:
        """
        Select provider based on complexity, choosing cheapest in tier.

        Complexity tiers:
        - 0-2: cheap models (<$1/M input)
        - 3-5: medium models ($1-5/M input)
        - 6+: powerful models (>$5/M input)
        """
        # Determine cost tier based on complexity
        if complexity <= 2:
            # Cheap tier (<$1/M input)
            tier_candidates = [c for c in candidates if c.input_cost_per_1k < 1.0]
        elif complexity <= 5:
            # Medium tier ($1-5/M input)
            tier_candidates = [c for c in candidates if 1.0 <= c.input_cost_per_1k <= 5.0]
        else:
            # Powerful tier (>$5/M input)
            tier_candidates = [c for c in candidates if c.input_cost_per_1k > 5.0]

        # If no candidates in tier, fall back to all candidates
        if not tier_candidates:
            tier_candidates = candidates

        # Sort by cost (cheapest first)
        tier_candidates.sort(key=lambda c: c.input_cost_per_1k + c.output_cost_per_1k)

        # Return cheapest
        return tier_candidates[0]

    def _build_fallback_chain(self, primary_provider_key: str) -> List[str]:
        """
        Build fallback chain for provider.

        Chain: [primary, claude-sonnet, openai-gpt-4o, claude-code-cli]
        """
        chain = [primary_provider_key]

        # Add reliable fallbacks
        fallbacks = ["claude-sonnet", "litellm/gpt-4o", "claude-code-cli"]

        for fallback in fallbacks:
            if fallback != primary_provider_key and fallback not in chain:
                chain.append(fallback)

        return chain

    def _estimate_cost(self,
                      provider: ProviderConfig,
                      estimated_input_tokens: int = 2000,
                      estimated_output_tokens: int = 1000) -> float:
        """
        Estimate cost for provider.

        Args:
            provider: Provider config
            estimated_input_tokens: Estimated input tokens (default: 2000)
            estimated_output_tokens: Estimated output tokens (default: 1000)

        Returns:
            Estimated cost in USD
        """
        input_cost = (estimated_input_tokens / 1000) * provider.input_cost_per_1k
        output_cost = (estimated_output_tokens / 1000) * provider.output_cost_per_1k
        return round(input_cost + output_cost, 4)

    def get_fallback_chain(self, provider_key: str) -> List[str]:
        """Get fallback chain for a provider"""
        return self._build_fallback_chain(provider_key)

    def list_providers(self, verbose: bool = False) -> List[Dict]:
        """List all configured providers"""
        providers_list = []

        for provider_key, provider in self.providers.items():
            provider_dict = {
                "key": provider_key,
                "name": provider.name,
                "model": provider.model,
                "enabled": provider.enabled,
                "input_cost": provider.input_cost_per_1k,
                "output_cost": provider.output_cost_per_1k
            }

            if verbose:
                provider_dict["capabilities"] = asdict(provider.capabilities)
                provider_dict["max_tokens"] = provider.max_tokens
                provider_dict["timeout"] = provider.timeout

            providers_list.append(provider_dict)

        return providers_list


class ProviderFallbackExecutor:
    """
    Executes provider requests with fallback chain and retry logic.

    Handles:
    - Fallback chain execution
    - Retry logic with exponential backoff
    - Provider failure tracking
    - Logging to provider_usage.jsonl
    """

    def __init__(self, selector: ProviderSelector, log_path: Optional[str] = None):
        """
        Initialize fallback executor.

        Args:
            selector: ProviderSelector instance
            log_path: Path to provider_usage.jsonl (optional)
        """
        self.selector = selector
        self.log_path = log_path or ".claude-loop/logs/provider_usage.jsonl"

    def execute_with_fallback(self,
                             provider_key: str,
                             messages: List[Dict],
                             max_retries: int = 3,
                             retry_delay: float = 1.0) -> Dict:
        """
        Execute request with fallback chain.

        Args:
            provider_key: Primary provider key
            messages: Messages to send to provider
            max_retries: Max retries per provider (default: 3)
            retry_delay: Initial retry delay in seconds (default: 1.0)

        Returns:
            Response dictionary with provider, model, response, etc.

        Raises:
            ProviderError: If all providers in fallback chain failed
        """
        fallback_chain = self.selector.get_fallback_chain(provider_key)

        for i, provider in enumerate(fallback_chain):
            is_fallback = i > 0

            for attempt in range(max_retries):
                try:
                    # Log attempt
                    self._log_attempt(provider, attempt, is_fallback)

                    # Execute provider request
                    # Note: Actual provider execution would go here
                    # For now, this is a placeholder that returns success
                    response = self._call_provider(provider, messages)

                    # Log success
                    self._log_success(provider, response, is_fallback)

                    return {
                        "provider": provider,
                        "response": response,
                        "fallback_used": is_fallback,
                        "attempts": attempt + 1
                    }

                except Exception as e:
                    # Log failure
                    self._log_failure(provider, e, attempt, is_fallback)

                    # If last attempt for this provider, move to next in chain
                    if attempt == max_retries - 1:
                        break

                    # Exponential backoff
                    delay = retry_delay * (2 ** attempt)
                    time.sleep(delay)

        # All providers failed
        raise Exception(f"All providers in fallback chain failed: {fallback_chain}")

    def _call_provider(self, provider_key: str, messages: List[Dict]) -> Dict:
        """
        Call provider (placeholder - actual implementation would integrate with providers).

        Args:
            provider_key: Provider key
            messages: Messages to send

        Returns:
            Response dictionary

        Raises:
            Exception: On provider error
        """
        # This is a placeholder that would be replaced with actual provider calls
        # In real implementation, this would call:
        # - lib/providers/litellm_provider.py for litellm/*
        # - lib/providers/openai_provider.py for openai
        # - lib/providers/gemini_provider.py for gemini
        # - etc.

        return {
            "content": "Placeholder response",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost": 0.01
        }

    def _log_attempt(self, provider: str, attempt: int, is_fallback: bool):
        """Log provider attempt"""
        status = "fallback" if is_fallback else "primary"
        print(f"[{status}] Attempting {provider} (attempt {attempt + 1})")

    def _log_success(self, provider: str, response: Dict, is_fallback: bool):
        """Log successful provider call"""
        print(f"[success] {provider} completed")

    def _log_failure(self, provider: str, error: Exception, attempt: int, is_fallback: bool):
        """Log failed provider call"""
        print(f"[failure] {provider} attempt {attempt + 1} failed: {error}")

    def log_provider_usage(self,
                          story_id: str,
                          iteration: int,
                          provider: str,
                          model: str,
                          complexity: int,
                          input_tokens: int,
                          output_tokens: int,
                          cost_usd: float,
                          latency_ms: float,
                          success: bool,
                          fallback_used: bool = False,
                          error: Optional[str] = None):
        """
        Log provider usage to provider_usage.jsonl.

        Args:
            story_id: Story ID
            iteration: Iteration number
            provider: Provider name
            model: Model name
            complexity: Task complexity (0-10)
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            cost_usd: Cost in USD
            latency_ms: Latency in milliseconds
            success: Whether request succeeded
            fallback_used: Whether fallback was used
            error: Error message (if failed)
        """
        # Ensure log directory exists
        log_dir = Path(self.log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log entry
        entry = {
            "timestamp": datetime.now().isoformat() + "Z",
            "story_id": story_id,
            "iteration": iteration,
            "provider": provider,
            "model": model,
            "complexity": complexity,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 4),
            "latency_ms": round(latency_ms, 2),
            "success": success,
            "fallback_used": fallback_used
        }

        if error:
            entry["error"] = str(error)

        # Append to log file
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + "\n")


def main():
    """CLI interface for provider selection"""
    parser = argparse.ArgumentParser(description="LLM Provider Selection")

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # select command
    select_parser = subparsers.add_parser('select', help='Select optimal provider')
    select_parser.add_argument('--complexity', type=int, required=True,
                              help='Task complexity (0-10)')
    select_parser.add_argument('--requires-vision', action='store_true',
                              help='Requires vision capability')
    select_parser.add_argument('--requires-tools', action='store_true',
                              help='Requires tool use capability')
    select_parser.add_argument('--requires-json-mode', action='store_true',
                              help='Requires JSON mode capability')
    select_parser.add_argument('--preferred', type=str,
                              help='Preferred provider key')
    select_parser.add_argument('--json', action='store_true',
                              help='Output as JSON')

    # fallback-chain command
    fallback_parser = subparsers.add_parser('fallback-chain',
                                           help='Get fallback chain for provider')
    fallback_parser.add_argument('--provider', type=str, required=True,
                                help='Provider key')

    # list command
    list_parser = subparsers.add_parser('list', help='List all providers')
    list_parser.add_argument('--verbose', action='store_true',
                            help='Show detailed information')
    list_parser.add_argument('--json', action='store_true',
                            help='Output as JSON')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    selector = ProviderSelector()

    if args.command == 'select':
        result = selector.select_provider(
            complexity=args.complexity,
            requires_vision=args.requires_vision,
            requires_tools=args.requires_tools,
            requires_json_mode=args.requires_json_mode,
            preferred_provider=args.preferred
        )

        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            print(f"Provider: {result.provider}")
            print(f"Model: {result.model}")
            print(f"Reasoning: {result.reasoning}")
            print(f"Fallback chain: {' -> '.join(result.fallback_chain)}")
            if result.cost_estimate:
                print(f"Estimated cost: ${result.cost_estimate:.4f}")
            print(f"Selection time: {result.selection_time_ms}ms")

    elif args.command == 'fallback-chain':
        chain = selector.get_fallback_chain(args.provider)
        print(' -> '.join(chain))

    elif args.command == 'list':
        providers = selector.list_providers(verbose=args.verbose)

        if args.json:
            print(json.dumps(providers, indent=2))
        else:
            print("\nConfigured Providers:")
            print("-" * 80)
            for provider in providers:
                status = "✓" if provider['enabled'] else "✗"
                print(f"{status} {provider['key']:<25} {provider['model']:<35} "
                      f"${provider['input_cost']:.2f}/${provider['output_cost']:.2f} per 1K")
            print()


if __name__ == '__main__':
    main()
