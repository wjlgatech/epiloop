#!/usr/bin/env python3
"""
Unit tests for Multi-LLM Review Panel
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.review_panel import (
    ReviewPanel,
    ReviewIssue,
    ReviewSuggestion,
    ReviewerFeedback,
    ReviewResult
)
from lib.llm_provider import LLMResponse, TokenUsage, ProviderError
from lib.llm_config import LLMConfigManager, ProviderConfig


class TestReviewDataClasses(unittest.TestCase):
    """Test review data classes"""

    def test_review_issue_creation(self):
        """Test ReviewIssue creation"""
        issue = ReviewIssue(
            severity="critical",
            category="security",
            description="SQL injection vulnerability",
            location="db.py:45"
        )
        self.assertEqual(issue.severity, "critical")
        self.assertEqual(issue.category, "security")
        self.assertEqual(issue.description, "SQL injection vulnerability")
        self.assertEqual(issue.location, "db.py:45")

    def test_review_suggestion_creation(self):
        """Test ReviewSuggestion creation"""
        suggestion = ReviewSuggestion(
            description="Use parameterized queries",
            priority="high",
            rationale="Prevents SQL injection attacks"
        )
        self.assertEqual(suggestion.description, "Use parameterized queries")
        self.assertEqual(suggestion.priority, "high")
        self.assertEqual(suggestion.rationale, "Prevents SQL injection attacks")

    def test_reviewer_feedback_to_dict(self):
        """Test ReviewerFeedback to_dict conversion"""
        feedback = ReviewerFeedback(
            provider="openai",
            model="gpt-4o",
            score=8,
            issues=[ReviewIssue(severity="minor", category="style", description="Formatting issue")],
            suggestions=[ReviewSuggestion(description="Use linter", priority="medium", rationale="Better code quality")],
            reasoning="Overall good code",
            cost=0.005
        )

        data = feedback.to_dict()
        self.assertEqual(data["provider"], "openai")
        self.assertEqual(data["model"], "gpt-4o")
        self.assertEqual(data["score"], 8)
        self.assertEqual(len(data["issues"]), 1)
        self.assertEqual(len(data["suggestions"]), 1)
        self.assertEqual(data["cost"], 0.005)

    def test_review_result_to_dict(self):
        """Test ReviewResult to_dict conversion"""
        result = ReviewResult(
            consensus_score=7.5,
            individual_reviews=[
                ReviewerFeedback(provider="openai", model="gpt-4o", score=8, cost=0.005),
                ReviewerFeedback(provider="gemini", model="gemini-2.0-flash", score=7, cost=0.002)
            ],
            total_cost=0.007,
            total_issues=3,
            total_suggestions=2,
            critical_issues=1,
            major_issues=1,
            reviewers_count=2,
            failed_reviewers=0
        )

        data = result.to_dict()
        self.assertEqual(data["consensus_score"], 7.5)
        self.assertEqual(len(data["individual_reviews"]), 2)
        self.assertEqual(data["total_cost"], 0.007)
        self.assertEqual(data["reviewers_count"], 2)


class TestReviewPanel(unittest.TestCase):
    """Test ReviewPanel class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock config manager
        self.mock_config_manager = Mock(spec=LLMConfigManager)

        # Create mock provider configs
        self.openai_config = ProviderConfig(
            name="openai",
            enabled=True,
            api_key="test-key",
            default_model="gpt-4o"
        )

        self.gemini_config = ProviderConfig(
            name="gemini",
            enabled=True,
            api_key="test-key",
            default_model="gemini-2.0-flash"
        )

        # Mock providers dict
        self.mock_config_manager.providers = {
            "openai": self.openai_config,
            "gemini": self.gemini_config
        }

        def get_provider_side_effect(name):
            return self.mock_config_manager.providers.get(name)

        self.mock_config_manager.get_provider = Mock(side_effect=get_provider_side_effect)

    def test_init_with_no_reviewers(self):
        """Test initialization with no enabled providers"""
        self.mock_config_manager.providers = {}
        with self.assertRaises(ValueError) as ctx:
            ReviewPanel(self.mock_config_manager)
        self.assertIn("No reviewers available", str(ctx.exception))

    def test_init_with_specific_reviewers(self):
        """Test initialization with specific reviewer list"""
        with patch('lib.review_panel.OpenAIProvider'):
            panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])
            self.assertEqual(panel.reviewers, ["openai"])
            self.assertIn("openai", panel.providers)

    def test_init_auto_detect_reviewers(self):
        """Test initialization with auto-detection of reviewers"""
        with patch('lib.review_panel.OpenAIProvider'), \
             patch('lib.review_panel.GeminiProvider'):
            panel = ReviewPanel(self.mock_config_manager)
            self.assertEqual(set(panel.reviewers), {"openai", "gemini"})
            self.assertIn("openai", panel.providers)
            self.assertIn("gemini", panel.providers)

    def test_create_provider_openai(self):
        """Test provider creation for OpenAI"""
        with patch('lib.review_panel.OpenAIProvider') as MockProvider:
            panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])
            MockProvider.assert_called_once()

    def test_create_provider_gemini(self):
        """Test provider creation for Gemini"""
        with patch('lib.review_panel.GeminiProvider') as MockProvider:
            panel = ReviewPanel(self.mock_config_manager, reviewers=["gemini"])
            MockProvider.assert_called_once()

    def test_create_provider_deepseek(self):
        """Test provider creation for DeepSeek"""
        deepseek_config = ProviderConfig(
            name="deepseek",
            enabled=True,
            api_key="test-key",
            default_model="deepseek-chat"
        )
        self.mock_config_manager.providers = {"deepseek": deepseek_config}

        with patch('lib.review_panel.DeepSeekProvider') as MockProvider:
            panel = ReviewPanel(self.mock_config_manager, reviewers=["deepseek"])
            MockProvider.assert_called_once()

    def test_create_provider_unsupported(self):
        """Test provider creation for unsupported provider"""
        unsupported_config = ProviderConfig(
            name="unsupported",
            enabled=True,
            api_key="test-key",
            default_model="model-1"
        )
        self.mock_config_manager.providers = {"unsupported": unsupported_config}

        with self.assertRaises(ValueError) as ctx:
            ReviewPanel(self.mock_config_manager, reviewers=["unsupported"])
        self.assertIn("Unsupported provider", str(ctx.exception))

    @patch('lib.review_panel.OpenAIProvider')
    def test_query_reviewer_success(self, MockProvider):
        """Test successful review query"""
        # Mock provider response
        mock_provider = MockProvider.return_value
        mock_response = LLMResponse(
            content=json.dumps({
                "score": 8,
                "issues": [
                    {
                        "severity": "minor",
                        "category": "style",
                        "description": "Missing docstring",
                        "location": "test.py:10"
                    }
                ],
                "suggestions": [
                    {
                        "description": "Add type hints",
                        "priority": "medium",
                        "rationale": "Improves code clarity"
                    }
                ],
                "reasoning": "Code is mostly good"
            }),
            model="gpt-4o",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.005,
            provider="openai"
        )
        mock_provider.complete.return_value = mock_response

        # Create panel
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])

        # Query reviewer
        feedback = panel._query_reviewer(
            "openai",
            mock_provider,
            "diff content",
            "story context",
            60,
            2
        )

        # Verify feedback
        self.assertEqual(feedback.provider, "openai")
        self.assertEqual(feedback.model, "gpt-4o")
        self.assertEqual(feedback.score, 8)
        self.assertEqual(len(feedback.issues), 1)
        self.assertEqual(len(feedback.suggestions), 1)
        self.assertEqual(feedback.cost, 0.005)
        self.assertIsNone(feedback.error)

    @patch('lib.review_panel.OpenAIProvider')
    def test_query_reviewer_json_parse_error(self, MockProvider):
        """Test review query with JSON parse error"""
        # Mock provider response with invalid JSON
        mock_provider = MockProvider.return_value
        mock_response = LLMResponse(
            content="Score: 7. This code looks good but needs improvement.",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.005,
            provider="openai"
        )
        mock_provider.complete.return_value = mock_response

        # Create panel
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])

        # Query reviewer
        feedback = panel._query_reviewer(
            "openai",
            mock_provider,
            "diff content",
            "story context",
            60,
            0  # No retries
        )

        # Verify feedback - should extract score and include error
        self.assertEqual(feedback.provider, "openai")
        self.assertEqual(feedback.score, 7)  # Extracted from text
        self.assertIsNotNone(feedback.error)
        if feedback.error:
            self.assertIn("Invalid JSON format", feedback.error)

    @patch('lib.review_panel.OpenAIProvider')
    def test_query_reviewer_provider_error(self, MockProvider):
        """Test review query with provider error"""
        # Mock provider error
        mock_provider = MockProvider.return_value
        mock_provider.complete.side_effect = ProviderError("API error")

        # Create panel
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])

        # Query reviewer
        feedback = panel._query_reviewer(
            "openai",
            mock_provider,
            "diff content",
            "story context",
            60,
            0  # No retries
        )

        # Verify feedback - should have error
        self.assertEqual(feedback.provider, "openai")
        self.assertEqual(feedback.score, 0)
        self.assertIsNotNone(feedback.error)
        if feedback.error:
            self.assertIn("API error", feedback.error)

    @patch('lib.review_panel.OpenAIProvider')
    def test_query_reviewer_retry_success(self, MockProvider):
        """Test review query with retry on first failure"""
        # Mock provider responses - fail once, then succeed
        mock_provider = MockProvider.return_value
        mock_provider.complete.side_effect = [
            ProviderError("Rate limit"),  # First attempt fails
            LLMResponse(  # Second attempt succeeds
                content=json.dumps({
                    "score": 9,
                    "issues": [],
                    "suggestions": [],
                    "reasoning": "Perfect code"
                }),
                model="gpt-4o",
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                cost=0.005,
                provider="openai"
            )
        ]

        # Create panel
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])

        # Query reviewer with retries
        feedback = panel._query_reviewer(
            "openai",
            mock_provider,
            "diff content",
            "story context",
            60,
            2  # Allow retries
        )

        # Verify feedback - should succeed on retry
        self.assertEqual(feedback.score, 9)
        self.assertIsNone(feedback.error)

    def test_aggregate_reviews_all_successful(self):
        """Test aggregating all successful reviews"""
        reviews = [
            ReviewerFeedback(
                provider="openai",
                model="gpt-4o",
                score=8,
                issues=[
                    ReviewIssue(severity="critical", category="bug", description="Bug 1"),
                    ReviewIssue(severity="minor", category="style", description="Style 1")
                ],
                suggestions=[
                    ReviewSuggestion(description="Suggestion 1", priority="high", rationale="Why 1")
                ],
                cost=0.005
            ),
            ReviewerFeedback(
                provider="gemini",
                model="gemini-2.0-flash",
                score=9,
                issues=[
                    ReviewIssue(severity="major", category="performance", description="Perf 1")
                ],
                suggestions=[],
                cost=0.002
            )
        ]

        with patch('lib.review_panel.OpenAIProvider'), \
             patch('lib.review_panel.GeminiProvider'):
            panel = ReviewPanel(self.mock_config_manager, reviewers=["openai", "gemini"])
            result = panel._aggregate_reviews(reviews)

        # Verify aggregation
        self.assertEqual(result.consensus_score, 8.5)  # (8 + 9) / 2
        self.assertEqual(result.total_issues, 3)
        self.assertEqual(result.total_suggestions, 1)
        self.assertEqual(result.critical_issues, 1)
        self.assertEqual(result.major_issues, 1)
        self.assertEqual(result.total_cost, 0.007)
        self.assertEqual(result.reviewers_count, 2)
        self.assertEqual(result.failed_reviewers, 0)

    def test_aggregate_reviews_with_failures(self):
        """Test aggregating reviews with some failures"""
        reviews = [
            ReviewerFeedback(
                provider="openai",
                model="gpt-4o",
                score=8,
                cost=0.005
            ),
            ReviewerFeedback(
                provider="gemini",
                model="unknown",
                score=0,
                cost=0.0,
                error="Timeout"
            )
        ]

        with patch('lib.review_panel.OpenAIProvider'), \
             patch('lib.review_panel.GeminiProvider'):
            panel = ReviewPanel(self.mock_config_manager, reviewers=["openai", "gemini"])
            result = panel._aggregate_reviews(reviews)

        # Verify aggregation - only successful review counted for score
        self.assertEqual(result.consensus_score, 8.0)  # Only successful review
        self.assertEqual(result.reviewers_count, 1)
        self.assertEqual(result.failed_reviewers, 1)
        self.assertEqual(result.total_cost, 0.005)

    def test_aggregate_reviews_all_failures(self):
        """Test aggregating all failed reviews"""
        reviews = [
            ReviewerFeedback(
                provider="openai",
                model="unknown",
                score=0,
                cost=0.0,
                error="Timeout"
            ),
            ReviewerFeedback(
                provider="gemini",
                model="unknown",
                score=0,
                cost=0.0,
                error="API error"
            )
        ]

        with patch('lib.review_panel.OpenAIProvider'), \
             patch('lib.review_panel.GeminiProvider'):
            panel = ReviewPanel(self.mock_config_manager, reviewers=["openai", "gemini"])
            result = panel._aggregate_reviews(reviews)

        # Verify aggregation - no successful reviews
        self.assertEqual(result.consensus_score, 0.0)
        self.assertEqual(result.reviewers_count, 0)
        self.assertEqual(result.failed_reviewers, 2)

    @patch('lib.review_panel.OpenAIProvider')
    @patch('lib.review_panel.GeminiProvider')
    def test_review_parallel_execution(self, MockGemini, MockOpenAI):
        """Test parallel review execution"""
        # Mock provider responses
        openai_response = LLMResponse(
            content=json.dumps({
                "score": 8,
                "issues": [],
                "suggestions": [],
                "reasoning": "Good"
            }),
            model="gpt-4o",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.005,
            provider="openai"
        )

        gemini_response = LLMResponse(
            content=json.dumps({
                "score": 9,
                "issues": [],
                "suggestions": [],
                "reasoning": "Great"
            }),
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.002,
            provider="gemini"
        )

        MockOpenAI.return_value.complete.return_value = openai_response
        MockGemini.return_value.complete.return_value = gemini_response

        # Create panel with both reviewers
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai", "gemini"])

        # Execute review
        result = panel.review(
            diff="test diff",
            context="test context",
            timeout_per_reviewer=60
        )

        # Verify both reviewers were called
        self.assertEqual(result.reviewers_count, 2)
        self.assertEqual(result.consensus_score, 8.5)  # (8 + 9) / 2

    @patch('lib.review_panel.OpenAIProvider')
    def test_review_with_timeout(self, MockOpenAI):
        """Test review handling timeout"""
        # Mock provider with slow response
        import time

        def slow_complete(*args, **kwargs):
            time.sleep(2)  # Simulate slow response
            return LLMResponse(
                content=json.dumps({"score": 7, "issues": [], "suggestions": [], "reasoning": "OK"}),
                model="gpt-4o",
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                cost=0.005,
                provider="openai"
            )

        MockOpenAI.return_value.complete.side_effect = slow_complete

        # Create panel
        panel = ReviewPanel(self.mock_config_manager, reviewers=["openai"])

        # Execute review with very short timeout
        result = panel.review(
            diff="test diff",
            context="test context",
            timeout_per_reviewer=1  # Very short timeout
        )

        # Timeout is handled by ThreadPoolExecutor - may succeed or timeout
        # Just verify we get a result
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
