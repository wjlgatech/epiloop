#!/usr/bin/env python3
"""
Unit tests for Reasoning Router
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.reasoning_router import (
    ReasoningRouter,
    TaskType,
    ReasoningLevel,
    TaskClassification,
    RoutingResult
)
from lib.llm_provider import Message, MessageRole, LLMResponse, TokenUsage
from lib.llm_config import LLMConfigManager, ProviderConfig


class TestReasoningRouter(unittest.TestCase):
    """Test cases for ReasoningRouter"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock config manager
        self.mock_config = MagicMock(spec=LLMConfigManager)

        # Mock provider configs
        self.deepseek_config = ProviderConfig(
            name='deepseek',
            api_key='test-key',
            default_model='deepseek-reasoner',
            enabled=True
        )

        self.openai_config = ProviderConfig(
            name='openai',
            api_key='test-key',
            default_model='o3-mini',
            enabled=True
        )

        # Mock get_provider method
        def mock_get_provider(name):
            if name == 'deepseek':
                return self.deepseek_config
            elif name == 'openai':
                return self.openai_config
            return None

        self.mock_config.get_provider = Mock(side_effect=mock_get_provider)

    def test_initialization(self):
        """Test router initialization"""
        router = ReasoningRouter(self.mock_config)
        self.assertIsNotNone(router)
        self.assertIsNotNone(router.config_manager)

    def test_initialization_default_config(self):
        """Test router initialization with default config manager"""
        with patch('lib.reasoning_router.LLMConfigManager'):
            router = ReasoningRouter()
            self.assertIsNotNone(router)

    def test_classify_math_task(self):
        """Test classification of math tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "Solve the quadratic equation 2x^2 + 5x - 3 = 0"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.MATH)
        self.assertIn(classification.reasoning_level, [ReasoningLevel.MEDIUM, ReasoningLevel.HIGH])
        self.assertGreater(classification.confidence, 0.5)
        self.assertTrue(any('solve' in kw or 'equation' in kw for kw in classification.keywords_found))

    def test_classify_logic_task(self):
        """Test classification of logic tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "If all humans are mortal and Socrates is human, deduce whether Socrates is mortal"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.LOGIC)
        self.assertGreater(classification.confidence, 0.5)

    def test_classify_planning_task(self):
        """Test classification of planning tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "Design a strategy for implementing a distributed caching system with multiple nodes"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.PLANNING)
        self.assertEqual(classification.reasoning_level, ReasoningLevel.HIGH)

    def test_classify_debugging_task(self):
        """Test classification of debugging tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "Debug this code: why does it crash with a null pointer exception?"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.DEBUGGING)
        self.assertGreater(classification.confidence, 0.5)

    def test_classify_coding_task(self):
        """Test classification of coding tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "Implement an efficient algorithm to find the longest common subsequence with O(n*m) complexity"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.CODING)
        self.assertEqual(classification.reasoning_level, ReasoningLevel.HIGH)

    def test_classify_general_task(self):
        """Test classification of general tasks"""
        router = ReasoningRouter(self.mock_config)

        task = "What is the capital of France?"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.GENERAL)
        self.assertEqual(classification.reasoning_level, ReasoningLevel.LOW)
        self.assertEqual(len(classification.keywords_found), 0)

    def test_reasoning_level_high(self):
        """Test high reasoning level detection"""
        router = ReasoningRouter(self.mock_config)

        task = ("Calculate the derivative of sin(x^2) and then integrate the result, "
                "proving each step with mathematical rigor and explaining the chain rule")
        classification = router.classify_task(task)

        self.assertEqual(classification.reasoning_level, ReasoningLevel.HIGH)
        self.assertGreater(classification.confidence, 0.8)

    def test_reasoning_level_medium(self):
        """Test medium reasoning level detection"""
        router = ReasoningRouter(self.mock_config)

        task = "Solve for x in the equation 2x + 5 = 15"
        classification = router.classify_task(task)

        self.assertIn(classification.reasoning_level, [ReasoningLevel.LOW, ReasoningLevel.MEDIUM])

    def test_model_recommendation_high_reasoning(self):
        """Test model recommendation for high reasoning tasks"""
        with patch('lib.reasoning_router.DeepSeekProvider'):
            with patch('lib.reasoning_router.OpenAIProvider'):
                router = ReasoningRouter(self.mock_config)
                # Mock providers
                router._providers = {
                    'o3-mini': Mock(),
                    'deepseek-reasoner': Mock()
                }

                task = "Prove the Pythagorean theorem using multiple geometric approaches"
                classification = router.classify_task(task)

                # Should prefer o3-mini for high reasoning
                self.assertEqual(classification.recommended_model, 'o3-mini')

    def test_model_recommendation_medium_reasoning(self):
        """Test model recommendation for medium reasoning tasks"""
        with patch('lib.reasoning_router.DeepSeekProvider'):
            with patch('lib.reasoning_router.OpenAIProvider'):
                router = ReasoningRouter(self.mock_config)
                # Mock providers
                router._providers = {
                    'o3-mini': Mock(),
                    'deepseek-reasoner': Mock()
                }

                task = "Calculate 15% of 200"
                classification = router.classify_task(task)

                # Should prefer deepseek-reasoner for cost-effectiveness
                self.assertEqual(classification.recommended_model, 'deepseek-reasoner')

    def test_model_recommendation_only_deepseek(self):
        """Test model recommendation when only DeepSeek available"""
        with patch('lib.reasoning_router.DeepSeekProvider'):
            router = ReasoningRouter(self.mock_config)
            router._providers = {'deepseek-reasoner': Mock()}

            task = "Prove the Pythagorean theorem"
            classification = router.classify_task(task)

            self.assertEqual(classification.recommended_model, 'deepseek-reasoner')

    def test_model_recommendation_only_o3(self):
        """Test model recommendation when only o3-mini available"""
        with patch('lib.reasoning_router.OpenAIProvider'):
            router = ReasoningRouter(self.mock_config)
            router._providers = {'o3-mini': Mock()}

            task = "Calculate 15% of 200"
            classification = router.classify_task(task)

            self.assertEqual(classification.recommended_model, 'o3-mini')

    def test_model_recommendation_no_providers(self):
        """Test model recommendation when no reasoning providers available"""
        with patch('lib.reasoning_router.DeepSeekProvider', side_effect=Exception):
            with patch('lib.reasoning_router.OpenAIProvider', side_effect=Exception):
                router = ReasoningRouter(self.mock_config)
                router._providers = {}

                task = "Solve x^2 = 16"
                classification = router.classify_task(task)

                # Should fallback to claude-sonnet
                self.assertEqual(classification.recommended_model, 'claude-sonnet')

    @patch('lib.reasoning_router.DeepSeekProvider')
    def test_route_with_deepseek(self, mock_provider_class):
        """Test routing to DeepSeek provider"""
        # Create mock provider instance
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        # Mock response
        mock_response = LLMResponse(
            content="The solution is x = 5",
            model="deepseek-reasoner",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.0001,
            provider="deepseek",
            finish_reason="stop",
            raw_response={'reasoning_content': 'Step 1: ... Step 2: ...'}
        )
        mock_provider.complete.return_value = mock_response
        mock_provider.get_reasoning_content.return_value = "Step 1: ... Step 2: ..."

        router = ReasoningRouter(self.mock_config)
        router._providers = {'deepseek-reasoner': mock_provider}

        task = "Solve 2x + 5 = 15"
        result = router.route(task)

        self.assertIsInstance(result, RoutingResult)
        self.assertEqual(result.model_used, 'deepseek-reasoner')
        self.assertEqual(result.provider_used, 'deepseek')
        self.assertEqual(result.response.content, "The solution is x = 5")
        self.assertIsNotNone(result.chain_of_thought)

    @patch('lib.reasoning_router.OpenAIProvider')
    def test_route_with_o3(self, mock_provider_class):
        """Test routing to o3-mini provider"""
        # Create mock provider instance
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        # Mock response
        mock_response = LLMResponse(
            content="The solution is x = 5",
            model="o3-mini",
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=0.0005,
            provider="openai",
            finish_reason="stop"
        )
        mock_provider.complete.return_value = mock_response

        router = ReasoningRouter(self.mock_config)
        router._providers = {'o3-mini': mock_provider}

        task = "Prove the Pythagorean theorem using multiple approaches"
        result = router.route(task)

        self.assertIsInstance(result, RoutingResult)
        self.assertEqual(result.model_used, 'o3-mini')
        self.assertEqual(result.provider_used, 'openai')
        self.assertEqual(result.response.content, "The solution is x = 5")

    def test_route_with_custom_messages(self):
        """Test routing with custom message list"""
        with patch('lib.reasoning_router.DeepSeekProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            mock_response = LLMResponse(
                content="Response",
                model="deepseek-reasoner",
                usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
                cost=0.0001,
                provider="deepseek"
            )
            mock_provider.complete.return_value = mock_response

            router = ReasoningRouter(self.mock_config)
            router._providers = {'deepseek-reasoner': mock_provider}

            messages = [
                Message(role=MessageRole.SYSTEM, content="You are a math tutor"),
                Message(role=MessageRole.USER, content="Solve 2x + 5 = 15")
            ]

            result = router.route("Math task", messages=messages)

            # Verify complete was called with custom messages
            mock_provider.complete.assert_called_once()
            call_args = mock_provider.complete.call_args
            self.assertEqual(len(call_args[1]['messages']), 2)

    def test_route_with_temperature(self):
        """Test routing with custom temperature"""
        with patch('lib.reasoning_router.DeepSeekProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            mock_response = LLMResponse(
                content="Response",
                model="deepseek-reasoner",
                usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
                cost=0.0001,
                provider="deepseek"
            )
            mock_provider.complete.return_value = mock_response

            router = ReasoningRouter(self.mock_config)
            router._providers = {'deepseek-reasoner': mock_provider}

            result = router.route("Math task", temperature=0.3)

            # Verify temperature was passed
            call_args = mock_provider.complete.call_args
            self.assertEqual(call_args[1]['temperature'], 0.3)

    def test_route_unavailable_model(self):
        """Test routing when recommended model is unavailable"""
        router = ReasoningRouter(self.mock_config)
        router._providers = {}

        task = "Solve x^2 = 16"

        with self.assertRaises(ValueError) as context:
            router.route(task)

        self.assertIn("not available", str(context.exception))

    def test_get_available_models(self):
        """Test getting available models"""
        with patch('lib.reasoning_router.DeepSeekProvider'):
            with patch('lib.reasoning_router.OpenAIProvider'):
                router = ReasoningRouter(self.mock_config)
                router._providers = {
                    'deepseek-reasoner': Mock(),
                    'o3-mini': Mock()
                }

                models = router.get_available_models()

                self.assertEqual(len(models), 2)
                self.assertIn('deepseek-reasoner', models)
                self.assertIn('o3-mini', models)

    def test_get_available_models_empty(self):
        """Test getting available models when none configured"""
        with patch('lib.reasoning_router.DeepSeekProvider', side_effect=Exception):
            with patch('lib.reasoning_router.OpenAIProvider', side_effect=Exception):
                router = ReasoningRouter(self.mock_config)

                models = router.get_available_models()

                self.assertEqual(len(models), 0)

    def test_get_provider_name(self):
        """Test getting provider name from model"""
        router = ReasoningRouter(self.mock_config)

        self.assertEqual(router._get_provider_name('deepseek-reasoner'), 'deepseek')
        self.assertEqual(router._get_provider_name('deepseek-chat'), 'deepseek')
        self.assertEqual(router._get_provider_name('o3-mini'), 'openai')
        self.assertEqual(router._get_provider_name('gpt-4o'), 'openai')
        self.assertEqual(router._get_provider_name('gemini-2.0-flash'), 'gemini')
        self.assertEqual(router._get_provider_name('unknown-model'), 'unknown')

    def test_keyword_matching_case_insensitive(self):
        """Test that keyword matching is case insensitive"""
        router = ReasoningRouter(self.mock_config)

        task = "SOLVE the EQUATION 2x + 5 = 15"
        classification = router.classify_task(task)

        self.assertEqual(classification.task_type, TaskType.MATH)

    def test_multiple_keyword_categories(self):
        """Test task with keywords from multiple categories"""
        router = ReasoningRouter(self.mock_config)

        task = "Debug the algorithm that calculates the fibonacci sequence"
        classification = router.classify_task(task)

        # Should classify as the category with most keywords
        self.assertIn(classification.task_type, [TaskType.DEBUGGING, TaskType.CODING])

    def test_classification_reasoning_generation(self):
        """Test that classification reasoning is generated"""
        router = ReasoningRouter(self.mock_config)

        task = "Solve the quadratic equation"
        classification = router.classify_task(task)

        self.assertIsNotNone(classification.reasoning)
        self.assertGreater(len(classification.reasoning), 0)
        self.assertIn('math', classification.reasoning.lower())

    def test_get_matching_keywords(self):
        """Test getting matching keywords"""
        router = ReasoningRouter(self.mock_config)

        task_lower = "solve the equation and calculate the result"
        keywords = router._get_matching_keywords(task_lower, TaskType.MATH)

        self.assertIn('solve', keywords)
        self.assertIn('equation', keywords)
        self.assertIn('calculate', keywords)

    def test_recommend_model_logic(self):
        """Test model recommendation logic"""
        with patch('lib.reasoning_router.DeepSeekProvider'):
            with patch('lib.reasoning_router.OpenAIProvider'):
                router = ReasoningRouter(self.mock_config)
                router._providers = {
                    'o3-mini': Mock(),
                    'deepseek-reasoner': Mock()
                }

                # High reasoning should prefer o3-mini
                model_high = router._recommend_model(ReasoningLevel.HIGH)
                self.assertEqual(model_high, 'o3-mini')

                # Medium reasoning should prefer deepseek-reasoner
                model_medium = router._recommend_model(ReasoningLevel.MEDIUM)
                self.assertEqual(model_medium, 'deepseek-reasoner')

                # Low reasoning should prefer deepseek-reasoner
                model_low = router._recommend_model(ReasoningLevel.LOW)
                self.assertEqual(model_low, 'deepseek-reasoner')


if __name__ == '__main__':
    unittest.main()
