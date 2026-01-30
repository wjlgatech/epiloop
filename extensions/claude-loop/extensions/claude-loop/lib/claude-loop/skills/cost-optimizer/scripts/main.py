#!/usr/bin/env python3
"""
cost-optimizer skill - Analyze story complexity and recommend models

Recommends optimal Claude model (Haiku/Sonnet/Opus) for each story.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

class CostOptimizer:
    """Analyzes stories and recommends optimal models."""

    COMPLEXITY_KEYWORDS = {
        'complex': ['security', 'architecture', 'algorithm', 'encryption', 'authentication', 'authorization'],
        'medium': ['refactor', 'test', 'api', 'integration', 'feature', 'implement'],
        'simple': ['docs', 'documentation', 'config', 'configuration', 'readme', 'comment']
    }

    PRICING = {
        'haiku': {'input': 0.25, 'output': 1.25},
        'sonnet': {'input': 3.00, 'output': 15.00},
        'opus': {'input': 15.00, 'output': 75.00}
    }

    def __init__(self, prd_path: str):
        self.prd_path = Path(prd_path)
        self.prd_data: Dict[str, Any] = {}
        self.analyses: List[Dict[str, Any]] = []

    def load_prd(self) -> bool:
        """Load PRD JSON file."""
        try:
            with open(self.prd_path, 'r') as f:
                self.prd_data = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading PRD: {e}")
            return False

    def calculate_complexity(self, story: Dict[str, Any]) -> int:
        """Calculate complexity score (0-100)."""
        score = 0

        # File scope count (25 points max)
        file_scope = len(story.get('fileScope', []))
        score += min(file_scope * 5, 25)

        # Acceptance criteria count (25 points max)
        criteria = len(story.get('acceptanceCriteria', []))
        score += min(criteria * 3, 25)

        # Keyword analysis (30 points max)
        text = (story.get('title', '') + ' ' + story.get('description', '')).lower()
        for keyword in self.COMPLEXITY_KEYWORDS['complex']:
            if keyword in text:
                score += 5
        for keyword in self.COMPLEXITY_KEYWORDS['simple']:
            if keyword in text:
                score -= 3

        # Description length (10 points max)
        desc_length = len(story.get('description', ''))
        score += min(desc_length // 50, 10)

        # Dependencies count (10 points max)
        deps = len(story.get('dependencies', []))
        score += min(deps * 3, 10)

        return max(0, min(score, 100))

    def recommend_model(self, complexity: int) -> str:
        """Recommend model based on complexity."""
        if complexity < 40:
            return 'haiku'
        elif complexity < 70:
            return 'sonnet'
        else:
            return 'opus'

    def estimate_cost(self, model: str, tokens_in: int = 5000, tokens_out: int = 2000) -> float:
        """Estimate cost for a story."""
        pricing = self.PRICING[model]
        cost = (tokens_in * pricing['input'] + tokens_out * pricing['output']) / 1_000_000
        return cost

    def analyze_stories(self) -> bool:
        """Analyze all stories in PRD."""
        if 'userStories' not in self.prd_data:
            print("Error: No user stories found in PRD")
            return False

        print("Cost Optimizer v1.0")
        print("=" * 50)
        print(f"PRD: {self.prd_path.name}")
        print(f"Stories: {len(self.prd_data['userStories'])}")
        print()

        total_cost = 0
        opus_cost = 0

        for story in self.prd_data['userStories']:
            story_id = story.get('id', 'Unknown')
            title = story.get('title', 'Untitled')

            complexity = self.calculate_complexity(story)
            recommended_model = self.recommend_model(complexity)

            cost = self.estimate_cost(recommended_model)
            opus_baseline = self.estimate_cost('opus')

            total_cost += cost
            opus_cost += opus_baseline

            analysis = {
                'id': story_id,
                'title': title,
                'complexity': complexity,
                'model': recommended_model,
                'cost': cost
            }
            self.analyses.append(analysis)

            print(f"  {story_id} [{recommended_model}]: {title[:50]}")
            print(f"    Complexity: {complexity}/100, Est. cost: ${cost:.2f}")
            print()

        savings = opus_cost - total_cost
        savings_pct = (savings / opus_cost * 100) if opus_cost > 0 else 0

        print("Summary:")
        print(f"  Total estimated cost: ${total_cost:.2f}")
        print(f"  Baseline (all-Opus): ${opus_cost:.2f}")
        print(f"  Savings: ${savings:.2f} ({savings_pct:.0f}%)")
        print()

        return True

    def optimize(self) -> bool:
        """Main optimization workflow."""
        if not self.load_prd():
            return False

        return self.analyze_stories()

def main():
    prd_path = sys.argv[1] if len(sys.argv) > 1 else "prd.json"

    optimizer = CostOptimizer(prd_path)
    success = optimizer.optimize()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
