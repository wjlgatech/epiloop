#!/usr/bin/env python3
"""
Multi-LLM Review Panel

Creates a review panel that queries multiple LLM providers in parallel to get
diverse perspectives on implemented code. Aggregates results into consensus scores.
"""

import json
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.llm_config import LLMConfigManager, ProviderConfig
from lib.llm_provider import Message, MessageRole, LLMResponse, ProviderError
from lib.providers.openai_provider import OpenAIProvider
from lib.providers.gemini_provider import GeminiProvider
from lib.providers.deepseek_provider import DeepSeekProvider


@dataclass
class ReviewIssue:
    """A specific issue identified by a reviewer"""
    severity: str  # "critical", "major", "minor"
    category: str  # "bug", "performance", "security", "style", "maintainability"
    description: str
    location: Optional[str] = None  # File/line reference if applicable


@dataclass
class ReviewSuggestion:
    """A suggestion for improvement"""
    description: str
    priority: str  # "high", "medium", "low"
    rationale: str


@dataclass
class ReviewerFeedback:
    """Feedback from a single reviewer"""
    provider: str
    model: str
    score: int  # 1-10
    issues: List[ReviewIssue] = field(default_factory=list)
    suggestions: List[ReviewSuggestion] = field(default_factory=list)
    reasoning: str = ""
    cost: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "provider": self.provider,
            "model": self.model,
            "score": self.score,
            "issues": [asdict(i) for i in self.issues],
            "suggestions": [asdict(s) for s in self.suggestions],
            "reasoning": self.reasoning,
            "cost": self.cost,
            "error": self.error
        }


@dataclass
class ReviewResult:
    """Aggregated review results from multiple reviewers"""
    consensus_score: float  # Average score across all reviewers
    individual_reviews: List[ReviewerFeedback] = field(default_factory=list)
    total_cost: float = 0.0
    total_issues: int = 0
    total_suggestions: int = 0
    critical_issues: int = 0
    major_issues: int = 0
    reviewers_count: int = 0
    failed_reviewers: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "consensus_score": self.consensus_score,
            "individual_reviews": [r.to_dict() for r in self.individual_reviews],
            "total_cost": self.total_cost,
            "total_issues": self.total_issues,
            "total_suggestions": self.total_suggestions,
            "critical_issues": self.critical_issues,
            "major_issues": self.major_issues,
            "reviewers_count": self.reviewers_count,
            "failed_reviewers": self.failed_reviewers
        }


class ReviewPanel:
    """Multi-LLM review panel for code review"""

    # Review prompt template
    REVIEW_PROMPT_TEMPLATE = """You are a code reviewer. Please review the following code changes and provide structured feedback.

Code Diff:
{diff}

Story Context:
{context}

Please provide your review in the following JSON format:
{{
    "score": <1-10>,
    "issues": [
        {{
            "severity": "critical|major|minor",
            "category": "bug|performance|security|style|maintainability",
            "description": "Description of the issue",
            "location": "Optional file:line reference"
        }}
    ],
    "suggestions": [
        {{
            "description": "Suggestion for improvement",
            "priority": "high|medium|low",
            "rationale": "Why this would be helpful"
        }}
    ],
    "reasoning": "Overall reasoning for your score and feedback"
}}

Focus on:
- Correctness and potential bugs
- Security vulnerabilities
- Performance issues
- Code quality and maintainability
- Test coverage

Respond ONLY with valid JSON."""

    def __init__(self, config_manager: Optional[LLMConfigManager] = None, reviewers: Optional[List[str]] = None):
        """
        Initialize review panel

        Args:
            config_manager: LLM configuration manager (loads default if None)
            reviewers: List of provider names to use as reviewers (uses all enabled if None)
        """
        self.config_manager = config_manager or LLMConfigManager()

        # Get all enabled providers if reviewers not specified
        if reviewers is None:
            self.reviewers = [name for name, config in self.config_manager.providers.items() if config.enabled]
        else:
            self.reviewers = reviewers

        # Validate that at least one reviewer is available
        if not self.reviewers:
            raise ValueError("No reviewers available. Enable at least one LLM provider.")

        # Initialize provider instances
        self.providers: Dict[str, Any] = {}
        for provider_name in self.reviewers:
            config = self.config_manager.get_provider(provider_name)
            if config and config.enabled:
                self.providers[provider_name] = self._create_provider(provider_name, config)

    def _create_provider(self, provider_name: str, config: ProviderConfig) -> Any:
        """Create provider instance based on name"""
        if provider_name == "openai":
            return OpenAIProvider(config)
        elif provider_name == "gemini":
            return GeminiProvider(config)
        elif provider_name == "deepseek":
            return DeepSeekProvider(config)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

    def review(
        self,
        diff: str,
        context: str,
        timeout_per_reviewer: int = 60,
        max_retries: int = 2
    ) -> ReviewResult:
        """
        Get reviews from all configured reviewers in parallel

        Args:
            diff: Code diff to review
            context: Story context (description, requirements)
            timeout_per_reviewer: Timeout for each reviewer in seconds
            max_retries: Maximum retries on failure

        Returns:
            ReviewResult with aggregated feedback
        """
        individual_reviews: List[ReviewerFeedback] = []

        # Query reviewers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            # Submit all review tasks
            future_to_provider = {
                executor.submit(
                    self._query_reviewer,
                    provider_name,
                    provider,
                    diff,
                    context,
                    timeout_per_reviewer,
                    max_retries
                ): provider_name
                for provider_name, provider in self.providers.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider, timeout=timeout_per_reviewer + 10):
                provider_name = future_to_provider[future]
                try:
                    review = future.result(timeout=5)  # Small timeout for getting result
                    individual_reviews.append(review)
                except FutureTimeoutError:
                    # Reviewer timed out - add error review
                    individual_reviews.append(ReviewerFeedback(
                        provider=provider_name,
                        model="unknown",
                        score=0,
                        error=f"Timeout after {timeout_per_reviewer}s"
                    ))
                except Exception as e:
                    # Reviewer failed - add error review
                    individual_reviews.append(ReviewerFeedback(
                        provider=provider_name,
                        model="unknown",
                        score=0,
                        error=str(e)
                    ))

        # Aggregate results
        return self._aggregate_reviews(individual_reviews)

    def _query_reviewer(
        self,
        provider_name: str,
        provider: Any,
        diff: str,
        context: str,
        timeout: int,
        max_retries: int
    ) -> ReviewerFeedback:
        """
        Query a single reviewer

        Args:
            provider_name: Name of provider
            provider: Provider instance
            diff: Code diff
            context: Story context
            timeout: Timeout in seconds (handled by ThreadPoolExecutor)
            max_retries: Maximum retries

        Returns:
            ReviewerFeedback from this reviewer
        """
        # Note: timeout is handled by ThreadPoolExecutor in review() method
        # Build review prompt
        prompt = self.REVIEW_PROMPT_TEMPLATE.format(
            diff=diff,
            context=context
        )

        messages = [Message(role=MessageRole.USER, content=prompt)]

        # Try to get review with retries
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Call provider with timeout
                response: LLMResponse = provider.complete(
                    messages=messages,
                    temperature=0.3,  # Low temperature for consistent reviews
                    max_tokens=2048
                )

                # Parse JSON response
                try:
                    review_data = json.loads(response.content)

                    # Extract structured data
                    issues = [
                        ReviewIssue(**issue_data)
                        for issue_data in review_data.get("issues", [])
                    ]

                    suggestions = [
                        ReviewSuggestion(**sugg_data)
                        for sugg_data in review_data.get("suggestions", [])
                    ]

                    return ReviewerFeedback(
                        provider=provider_name,
                        model=response.model,
                        score=review_data.get("score", 5),
                        issues=issues,
                        suggestions=suggestions,
                        reasoning=review_data.get("reasoning", ""),
                        cost=response.cost
                    )

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    # JSON parsing failed - try to extract score at least
                    last_error = f"Failed to parse JSON response: {e}"

                    # Attempt to extract a numeric score from text
                    import re
                    score_match = re.search(r'(?:score|rating)[\s:]+(\d+)', response.content.lower())
                    score = int(score_match.group(1)) if score_match else 5

                    return ReviewerFeedback(
                        provider=provider_name,
                        model=response.model,
                        score=score,
                        reasoning=response.content[:500],  # First 500 chars
                        cost=response.cost,
                        error=f"Invalid JSON format (attempt {attempt + 1}/{max_retries + 1})"
                    )

            except ProviderError as e:
                last_error = str(e)
                if attempt < max_retries:
                    continue  # Retry

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    continue  # Retry

        # All retries failed
        return ReviewerFeedback(
            provider=provider_name,
            model="unknown",
            score=0,
            error=f"Failed after {max_retries + 1} attempts: {last_error}"
        )

    def _aggregate_reviews(self, reviews: List[ReviewerFeedback]) -> ReviewResult:
        """
        Aggregate individual reviews into consensus result

        Args:
            reviews: List of individual reviews

        Returns:
            Aggregated ReviewResult
        """
        # Filter out failed reviews for score calculation
        successful_reviews = [r for r in reviews if r.error is None]
        failed_count = len(reviews) - len(successful_reviews)

        # Calculate consensus score (average of successful reviews)
        if successful_reviews:
            consensus_score = sum(r.score for r in successful_reviews) / len(successful_reviews)
        else:
            consensus_score = 0.0

        # Count total issues and suggestions
        total_issues = sum(len(r.issues) for r in successful_reviews)
        total_suggestions = sum(len(r.suggestions) for r in successful_reviews)

        # Count critical and major issues
        critical_issues = sum(
            1 for r in successful_reviews
            for issue in r.issues
            if issue.severity == "critical"
        )
        major_issues = sum(
            1 for r in successful_reviews
            for issue in r.issues
            if issue.severity == "major"
        )

        # Calculate total cost
        total_cost = sum(r.cost for r in reviews)

        return ReviewResult(
            consensus_score=round(consensus_score, 2),
            individual_reviews=reviews,
            total_cost=round(total_cost, 6),
            total_issues=total_issues,
            total_suggestions=total_suggestions,
            critical_issues=critical_issues,
            major_issues=major_issues,
            reviewers_count=len(successful_reviews),
            failed_reviewers=failed_count
        )


def main():
    """CLI interface for review panel"""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-LLM Review Panel")
    parser.add_argument("command", choices=["review", "list-reviewers", "test"],
                        help="Command to execute")
    parser.add_argument("--diff", type=str, help="Path to diff file")
    parser.add_argument("--context", type=str, help="Story context")
    parser.add_argument("--reviewers", type=str, help="Comma-separated list of reviewers")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per reviewer (seconds)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Initialize config manager
    config_manager = LLMConfigManager()

    if args.command == "list-reviewers":
        # List available reviewers
        reviewers = [name for name, config in config_manager.providers.items() if config.enabled]
        if args.json:
            print(json.dumps({"reviewers": reviewers}, indent=2))
        else:
            print("Available Reviewers:")
            for reviewer in reviewers:
                config = config_manager.get_provider(reviewer)
                if config:
                    print(f"  - {reviewer} ({config.default_model})")
                else:
                    print(f"  - {reviewer} (config not found)")

    elif args.command == "test":
        # Test review panel with sample data
        sample_diff = """
diff --git a/lib/example.py b/lib/example.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/lib/example.py
@@ -0,0 +1,5 @@
+def divide(a, b):
+    return a / b
+
+result = divide(10, 0)
+print(result)
"""
        sample_context = "Add divide function with basic error handling"

        # Parse reviewers
        reviewers = args.reviewers.split(",") if args.reviewers else None

        # Create panel and review
        panel = ReviewPanel(config_manager, reviewers)
        result = panel.review(sample_diff, sample_context, timeout_per_reviewer=args.timeout)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"REVIEW RESULTS")
            print(f"{'='*60}")
            print(f"Consensus Score: {result.consensus_score}/10")
            print(f"Reviewers: {result.reviewers_count} successful, {result.failed_reviewers} failed")
            print(f"Total Cost: ${result.total_cost:.6f}")
            print(f"Issues: {result.total_issues} ({result.critical_issues} critical, {result.major_issues} major)")
            print(f"Suggestions: {result.total_suggestions}")
            print()

            for review in result.individual_reviews:
                print(f"\n--- {review.provider.upper()} ({review.model}) ---")
                print(f"Score: {review.score}/10")
                if review.error:
                    print(f"Error: {review.error}")
                else:
                    if review.issues:
                        print(f"Issues: {len(review.issues)}")
                        for issue in review.issues[:3]:  # Show first 3
                            print(f"  - [{issue.severity}] {issue.category}: {issue.description[:80]}")
                    if review.suggestions:
                        print(f"Suggestions: {len(review.suggestions)}")
                        for sugg in review.suggestions[:2]:  # Show first 2
                            print(f"  - [{sugg.priority}] {sugg.description[:80]}")

    elif args.command == "review":
        # Review actual diff
        if not args.diff or not args.context:
            print("Error: --diff and --context are required for review command")
            sys.exit(1)

        # Read diff from file
        diff_path = Path(args.diff)
        if not diff_path.exists():
            print(f"Error: Diff file not found: {args.diff}")
            sys.exit(1)

        with open(diff_path, 'r') as f:
            diff = f.read()

        # Parse reviewers
        reviewers = args.reviewers.split(",") if args.reviewers else None

        # Create panel and review
        panel = ReviewPanel(config_manager, reviewers)
        result = panel.review(diff, args.context, timeout_per_reviewer=args.timeout)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nConsensus Score: {result.consensus_score}/10")
            print(f"Total Issues: {result.total_issues}")
            print(f"Critical Issues: {result.critical_issues}")
            print(f"Total Cost: ${result.total_cost:.6f}")


if __name__ == "__main__":
    main()
