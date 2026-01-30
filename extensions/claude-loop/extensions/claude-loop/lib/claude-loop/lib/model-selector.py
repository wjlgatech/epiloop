#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/model-selector.py - Intelligent Model Selection for Claude-Loop

Automatically selects the most cost-effective model (haiku/sonnet/opus) for each
user story based on complexity analysis and heuristics.

Features:
- Complexity analysis based on file count, criteria count, and keywords
- Support for manual override via suggestedModel field
- Multiple model strategies (auto/always-opus/always-sonnet/always-haiku)
- Detailed reasoning in verbose mode
- Cost savings tracking and estimation

Pricing (as of 2025):
- Haiku:  $0.25/M input,  $1.25/M output (~60x cheaper than Opus)
- Sonnet: $3/M input,     $15/M output   (~5x cheaper than Opus)
- Opus:   $15/M input,    $75/M output   (baseline)

Usage:
    python3 lib/model-selector.py [command] [options]

Commands:
    select <story_id> [prd_file]    - Select model for a specific story
    analyze [prd_file]              - Analyze all stories and show model recommendations
    estimate-savings [prd_file]     - Estimate cost savings vs all-opus baseline

Options:
    --strategy STRATEGY             - Model strategy: auto|always-opus|always-sonnet|always-haiku
    --json                          - Output in JSON format
    --verbose                       - Show detailed reasoning
"""

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Model(Enum):
    """Available Claude models with relative cost multipliers."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"

    @property
    def cost_multiplier(self) -> float:
        """Return relative cost compared to Opus (1.0)."""
        multipliers = {
            Model.HAIKU: 0.017,   # ~60x cheaper
            Model.SONNET: 0.2,   # ~5x cheaper
            Model.OPUS: 1.0,
        }
        return multipliers[self]

    @property
    def pricing(self) -> dict[str, float]:
        """Return pricing per million tokens."""
        prices = {
            Model.HAIKU: {"input": 0.25, "output": 1.25},
            Model.SONNET: {"input": 3.0, "output": 15.0},
            Model.OPUS: {"input": 15.0, "output": 75.0},
        }
        return prices[self]


class Complexity(Enum):
    """Story complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class Strategy(Enum):
    """Model selection strategies."""
    AUTO = "auto"
    ALWAYS_OPUS = "always-opus"
    ALWAYS_SONNET = "always-sonnet"
    ALWAYS_HAIKU = "always-haiku"


# Keywords that suggest higher complexity (require better models)
COMPLEX_KEYWORDS = {
    # Architecture/design keywords
    "architect", "design", "refactor", "redesign", "migration",
    "infrastructure", "scalability", "microservice",
    # Security keywords
    "security", "authentication", "authorization", "encryption",
    "vulnerability", "audit", "compliance", "oauth", "jwt",
    # Complex features
    "concurrent", "parallel", "async", "distributed", "real-time",
    "caching", "optimization", "performance",
    # Integration keywords
    "api", "integration", "webhook", "third-party",
    # Database keywords
    "database", "migration", "schema", "transaction",
}

# Keywords that suggest simpler tasks (can use cheaper models)
SIMPLE_KEYWORDS = {
    # Documentation
    "document", "readme", "comment", "docstring",
    # Config/setup
    "config", "configuration", "setup", "environment",
    # Minor changes
    "rename", "typo", "fix", "update", "bump",
    # Tests
    "test", "unittest", "pytest", "spec",
    # Formatting
    "format", "lint", "style",
}


@dataclass
class SelectionResult:
    """Result of model selection for a story."""
    story_id: str
    selected_model: Model
    complexity: Complexity
    strategy_used: Strategy
    manual_override: bool
    reasoning: list[str] = field(default_factory=list)
    scores: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "story_id": self.story_id,
            "selected_model": self.selected_model.value,
            "complexity": self.complexity.value,
            "strategy_used": self.strategy_used.value,
            "manual_override": self.manual_override,
            "reasoning": self.reasoning,
            "scores": self.scores,
        }


class ModelSelector:
    """Intelligent model selector for user stories."""

    def __init__(self, prd_data: dict, strategy: Strategy = Strategy.AUTO):
        """
        Initialize model selector.

        Args:
            prd_data: Parsed PRD JSON data
            strategy: Model selection strategy to use
        """
        self.prd = prd_data
        self.stories = {s["id"]: s for s in prd_data.get("userStories", [])}
        self.strategy = strategy

        # Get parallelization config
        self.parallel_config = prd_data.get("parallelization", {})
        self.default_model = Model(self.parallel_config.get("defaultModel", "sonnet"))

        # Override strategy from PRD config if set
        config_strategy = self.parallel_config.get("modelStrategy")
        if config_strategy:
            self.strategy = Strategy(config_strategy)

    def select_model(self, story_id: str, verbose: bool = False) -> SelectionResult:
        """
        Select the optimal model for a given story.

        Args:
            story_id: ID of the story to analyze
            verbose: If True, include detailed reasoning

        Returns:
            SelectionResult with model selection and reasoning
        """
        if story_id not in self.stories:
            raise ValueError(f"Story not found: {story_id}")

        story = self.stories[story_id]
        reasoning = []
        scores = {}

        # Check for manual override first
        suggested = story.get("suggestedModel")
        if suggested:
            model = Model(suggested)
            complexity = Complexity(story.get("estimatedComplexity", "medium"))
            reasoning.append(f"Manual override: suggestedModel={suggested}")
            return SelectionResult(
                story_id=story_id,
                selected_model=model,
                complexity=complexity,
                strategy_used=self.strategy,
                manual_override=True,
                reasoning=reasoning,
                scores=scores,
            )

        # Check for fixed strategy
        if self.strategy != Strategy.AUTO:
            model = self._get_model_for_strategy()
            complexity = self._analyze_complexity(story)
            reasoning.append(f"Fixed strategy: {self.strategy.value}")
            return SelectionResult(
                story_id=story_id,
                selected_model=model,
                complexity=complexity,
                strategy_used=self.strategy,
                manual_override=False,
                reasoning=reasoning,
                scores=scores,
            )

        # Auto selection based on complexity analysis
        complexity = self._analyze_complexity(story)
        scores = self._compute_complexity_scores(story)

        if verbose:
            reasoning.append(f"Complexity scores: {scores}")

        # Determine explicit complexity from schema if set
        explicit_complexity = story.get("estimatedComplexity")
        if explicit_complexity:
            complexity = Complexity(explicit_complexity)
            reasoning.append(f"Using explicit complexity: {explicit_complexity}")

        # Map complexity to model
        model = self._complexity_to_model(complexity)
        reasoning.append(f"Analyzed complexity: {complexity.value} -> model: {model.value}")

        return SelectionResult(
            story_id=story_id,
            selected_model=model,
            complexity=complexity,
            strategy_used=self.strategy,
            manual_override=False,
            reasoning=reasoning,
            scores=scores,
        )

    def _get_model_for_strategy(self) -> Model:
        """Get model for fixed strategy."""
        strategy_map = {
            Strategy.ALWAYS_OPUS: Model.OPUS,
            Strategy.ALWAYS_SONNET: Model.SONNET,
            Strategy.ALWAYS_HAIKU: Model.HAIKU,
        }
        return strategy_map.get(self.strategy, self.default_model)

    def _analyze_complexity(self, story: dict) -> Complexity:
        """
        Analyze story complexity using heuristics.

        Factors considered:
        1. File scope count
        2. Acceptance criteria count
        3. Keyword analysis (complex vs simple)
        4. Description length
        5. Dependency count
        """
        scores = self._compute_complexity_scores(story)

        # Weighted scoring
        total_score = (
            scores["file_scope_score"] * 0.25 +
            scores["criteria_score"] * 0.25 +
            scores["keyword_score"] * 0.30 +
            scores["description_score"] * 0.10 +
            scores["dependency_score"] * 0.10
        )

        # Map score to complexity
        if total_score >= 0.7:
            return Complexity.COMPLEX
        elif total_score >= 0.4:
            return Complexity.MEDIUM
        else:
            return Complexity.SIMPLE

    def _compute_complexity_scores(self, story: dict) -> dict[str, float]:
        """Compute individual complexity scores for a story."""
        scores = {}

        # 1. File scope score (0-1)
        file_scope = story.get("fileScope", [])
        file_count = len(file_scope)
        if file_count >= 5:
            scores["file_scope_score"] = 1.0
        elif file_count >= 3:
            scores["file_scope_score"] = 0.7
        elif file_count >= 1:
            scores["file_scope_score"] = 0.4
        else:
            scores["file_scope_score"] = 0.2

        # 2. Acceptance criteria score (0-1)
        criteria = story.get("acceptanceCriteria", [])
        criteria_count = len(criteria)
        if criteria_count >= 7:
            scores["criteria_score"] = 1.0
        elif criteria_count >= 5:
            scores["criteria_score"] = 0.7
        elif criteria_count >= 3:
            scores["criteria_score"] = 0.4
        else:
            scores["criteria_score"] = 0.2

        # 3. Keyword score (-1 to 1, normalized to 0-1)
        text = self._get_story_text(story).lower()
        complex_hits = sum(1 for kw in COMPLEX_KEYWORDS if kw in text)
        simple_hits = sum(1 for kw in SIMPLE_KEYWORDS if kw in text)
        keyword_score = (complex_hits - simple_hits) / max(len(COMPLEX_KEYWORDS), 1)
        scores["keyword_score"] = max(0, min(1, (keyword_score + 1) / 2))

        # 4. Description length score (0-1)
        description = story.get("description", "")
        title = story.get("title", "")
        text_length = len(description) + len(title)
        if text_length >= 500:
            scores["description_score"] = 1.0
        elif text_length >= 200:
            scores["description_score"] = 0.6
        else:
            scores["description_score"] = 0.3

        # 5. Dependency score (0-1)
        deps = story.get("dependencies", [])
        dep_count = len(deps)
        if dep_count >= 3:
            scores["dependency_score"] = 1.0
        elif dep_count >= 1:
            scores["dependency_score"] = 0.5
        else:
            scores["dependency_score"] = 0.2

        return scores

    def _get_story_text(self, story: dict) -> str:
        """Get all text content from a story for analysis."""
        parts = [
            story.get("title", ""),
            story.get("description", ""),
        ]
        criteria = story.get("acceptanceCriteria", [])
        parts.extend(criteria)
        return " ".join(parts)

    def _complexity_to_model(self, complexity: Complexity) -> Model:
        """Map complexity to recommended model."""
        mapping = {
            Complexity.SIMPLE: Model.HAIKU,
            Complexity.MEDIUM: Model.SONNET,
            Complexity.COMPLEX: Model.OPUS,
        }
        return mapping[complexity]

    def analyze_all_stories(self, verbose: bool = False,
                            incomplete_only: bool = True) -> list[SelectionResult]:
        """
        Analyze all stories and return model recommendations.

        Args:
            verbose: Include detailed reasoning
            incomplete_only: Only analyze incomplete stories

        Returns:
            List of SelectionResult for each story
        """
        results = []
        for story_id, story in self.stories.items():
            if incomplete_only and story.get("passes", False):
                continue
            results.append(self.select_model(story_id, verbose=verbose))
        return results

    def estimate_cost_savings(self, tokens_per_story: int = 50000) -> dict[str, Any]:
        """
        Estimate cost savings compared to all-opus baseline.

        Args:
            tokens_per_story: Estimated average tokens per story (input + output)

        Returns:
            Dictionary with cost estimates and savings
        """
        results = self.analyze_all_stories(incomplete_only=True)

        # Calculate costs
        opus_baseline_cost = 0.0
        optimized_cost = 0.0

        model_counts = {Model.HAIKU: 0, Model.SONNET: 0, Model.OPUS: 0}

        for result in results:
            model = result.selected_model
            model_counts[model] += 1

            # Estimate cost (assume 60% input, 40% output)
            input_tokens = tokens_per_story * 0.6
            output_tokens = tokens_per_story * 0.4

            # Opus baseline
            opus_input = (input_tokens / 1_000_000) * Model.OPUS.pricing["input"]
            opus_output = (output_tokens / 1_000_000) * Model.OPUS.pricing["output"]
            opus_baseline_cost += opus_input + opus_output

            # Optimized cost
            opt_input = (input_tokens / 1_000_000) * model.pricing["input"]
            opt_output = (output_tokens / 1_000_000) * model.pricing["output"]
            optimized_cost += opt_input + opt_output

        savings = opus_baseline_cost - optimized_cost
        savings_pct = (savings / opus_baseline_cost * 100) if opus_baseline_cost > 0 else 0

        return {
            "story_count": len(results),
            "model_distribution": {k.value: v for k, v in model_counts.items()},
            "tokens_per_story": tokens_per_story,
            "opus_baseline_cost_usd": round(opus_baseline_cost, 4),
            "optimized_cost_usd": round(optimized_cost, 4),
            "savings_usd": round(savings, 4),
            "savings_percent": round(savings_pct, 1),
        }


def load_prd(prd_file: str) -> dict:
    """Load and parse PRD JSON file."""
    try:
        with open(prd_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: PRD file not found: {prd_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in PRD file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_select(story_id: str, prd_file: str, strategy: Strategy,
               json_output: bool, verbose: bool) -> None:
    """Select model for a specific story."""
    prd = load_prd(prd_file)
    selector = ModelSelector(prd, strategy=strategy)

    try:
        result = selector.select_model(story_id, verbose=verbose)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Story: {result.story_id}")
        print(f"Selected Model: {result.selected_model.value}")
        print(f"Complexity: {result.complexity.value}")
        print(f"Strategy: {result.strategy_used.value}")
        if result.manual_override:
            print("Note: Manual override via suggestedModel")
        if verbose and result.reasoning:
            print("\nReasoning:")
            for reason in result.reasoning:
                print(f"  - {reason}")


def cmd_analyze(prd_file: str, strategy: Strategy, json_output: bool,
                verbose: bool, incomplete_only: bool) -> None:
    """Analyze all stories and show model recommendations."""
    prd = load_prd(prd_file)
    selector = ModelSelector(prd, strategy=strategy)
    results = selector.analyze_all_stories(verbose=verbose, incomplete_only=incomplete_only)

    if json_output:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2))
    else:
        print("Model Recommendations")
        print("=" * 60)
        print()

        # Group by model
        by_model = {Model.HAIKU: [], Model.SONNET: [], Model.OPUS: []}
        for r in results:
            by_model[r.selected_model].append(r)

        for model in [Model.HAIKU, Model.SONNET, Model.OPUS]:
            stories = by_model[model]
            if stories:
                print(f"{model.value.upper()} ({len(stories)} stories):")
                print("-" * 40)
                for r in stories:
                    story = selector.stories[r.story_id]
                    title = story.get("title", "Untitled")[:35]
                    override = " [override]" if r.manual_override else ""
                    print(f"  {r.story_id}: {title} ({r.complexity.value}){override}")
                print()

        # Summary
        print("=" * 60)
        print(f"Total: {len(results)} stories")
        print(f"  Haiku:  {len(by_model[Model.HAIKU])} ({len(by_model[Model.HAIKU])/len(results)*100:.0f}%)" if results else "")
        print(f"  Sonnet: {len(by_model[Model.SONNET])} ({len(by_model[Model.SONNET])/len(results)*100:.0f}%)" if results else "")
        print(f"  Opus:   {len(by_model[Model.OPUS])} ({len(by_model[Model.OPUS])/len(results)*100:.0f}%)" if results else "")


def cmd_estimate_savings(prd_file: str, strategy: Strategy, json_output: bool) -> None:
    """Estimate cost savings vs all-opus baseline."""
    prd = load_prd(prd_file)
    selector = ModelSelector(prd, strategy=strategy)
    estimate = selector.estimate_cost_savings()

    if json_output:
        print(json.dumps(estimate, indent=2))
    else:
        print("Cost Savings Estimate")
        print("=" * 60)
        print()
        print(f"Stories to process: {estimate['story_count']}")
        print(f"Tokens per story:   {estimate['tokens_per_story']:,}")
        print()
        print("Model Distribution:")
        dist = estimate["model_distribution"]
        total = estimate["story_count"]
        for model, count in dist.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {model.capitalize():8} {count:3} ({pct:5.1f}%)")
        print()
        print("Cost Comparison:")
        print(f"  All-Opus baseline: ${estimate['opus_baseline_cost_usd']:.4f}")
        print(f"  Optimized cost:    ${estimate['optimized_cost_usd']:.4f}")
        print(f"  Savings:           ${estimate['savings_usd']:.4f} ({estimate['savings_percent']:.1f}%)")
        print()
        print("=" * 60)


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ["-h", "--help"]:
        print(__doc__)
        sys.exit(0)

    command = args[0]
    prd_file = "prd.json"
    story_id = None
    strategy = Strategy.AUTO
    json_output = False
    verbose = False
    incomplete_only = True

    # Parse arguments
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            json_output = True
        elif arg == "--verbose":
            verbose = True
        elif arg == "--strategy" and i + 1 < len(args):
            i += 1
            strategy = Strategy(args[i])
        elif arg == "--all":
            incomplete_only = False
        elif not arg.startswith("-"):
            if command == "select" and story_id is None:
                story_id = arg
            else:
                prd_file = arg
        i += 1

    if command == "select":
        if not story_id:
            print("Error: Story ID required for select command", file=sys.stderr)
            print("Usage: model-selector.py select <story_id> [prd_file]", file=sys.stderr)
            sys.exit(1)
        cmd_select(story_id, prd_file, strategy, json_output, verbose)
    elif command == "analyze":
        cmd_analyze(prd_file, strategy, json_output, verbose, incomplete_only)
    elif command == "estimate-savings":
        cmd_estimate_savings(prd_file, strategy, json_output)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Use --help for usage information.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
