#!/usr/bin/env python3
"""
Reasoning Task Router

Routes complex reasoning tasks to specialized models (o3-mini, DeepSeek-R1).
Automatically detects reasoning-heavy tasks and selects the best model.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.llm_config import LLMConfigManager
from lib.llm_provider import Message, MessageRole, LLMResponse
from lib.providers.deepseek_provider import DeepSeekProvider
from lib.providers.openai_provider import OpenAIProvider


class TaskType(str, Enum):
    """Types of tasks for classification"""
    MATH = "math"
    LOGIC = "logic"
    PLANNING = "planning"
    DEBUGGING = "debugging"
    CODING = "coding"
    GENERAL = "general"


class ReasoningLevel(str, Enum):
    """Reasoning complexity levels"""
    LOW = "low"           # Simple, direct tasks
    MEDIUM = "medium"     # Moderate reasoning required
    HIGH = "high"         # Complex reasoning required


@dataclass
class TaskClassification:
    """Result of task classification"""
    task_type: TaskType
    reasoning_level: ReasoningLevel
    confidence: float  # 0.0 - 1.0
    keywords_found: List[str]
    recommended_model: str
    reasoning: str


@dataclass
class RoutingResult:
    """Result of routing a task"""
    task_classification: TaskClassification
    response: LLMResponse
    model_used: str
    provider_used: str
    chain_of_thought: Optional[str] = None


class ReasoningRouter:
    """Routes tasks to appropriate reasoning models"""

    # Keywords indicating reasoning-heavy tasks
    MATH_KEYWORDS = [
        'calculate', 'compute', 'solve', 'equation', 'formula', 'theorem',
        'proof', 'derive', 'integrate', 'differentiate', 'algebra', 'geometry',
        'trigonometry', 'probability', 'statistics', 'optimization'
    ]

    LOGIC_KEYWORDS = [
        'logic', 'reasoning', 'infer', 'deduce', 'conclude', 'prove',
        'contradict', 'paradox', 'fallacy', 'syllogism', 'if-then',
        'necessary', 'sufficient', 'imply', 'entail'
    ]

    PLANNING_KEYWORDS = [
        'plan', 'strategy', 'approach', 'steps', 'procedure', 'algorithm',
        'workflow', 'process', 'schedule', 'organize', 'structure',
        'design', 'architect', 'blueprint', 'roadmap'
    ]

    DEBUGGING_KEYWORDS = [
        'debug', 'diagnose', 'troubleshoot', 'fix', 'error', 'bug',
        'issue', 'problem', 'wrong', 'incorrect', 'failure', 'crash',
        'exception', 'trace', 'root cause', 'why is', 'why does'
    ]

    CODING_KEYWORDS = [
        'implement', 'code', 'function', 'class', 'algorithm', 'optimize',
        'refactor', 'complexity', 'time complexity', 'space complexity',
        'data structure', 'performance', 'efficient'
    ]

    def __init__(self, config_manager: Optional[LLMConfigManager] = None):
        """Initialize reasoning router

        Args:
            config_manager: Optional config manager (creates default if not provided)
        """
        self.config_manager = config_manager or LLMConfigManager()
        self._providers: Dict[str, Any] = {}
        self._load_providers()

    def _load_providers(self):
        """Load available reasoning providers"""
        # Try to load DeepSeek-R1 provider
        try:
            deepseek_config = self.config_manager.get_provider('deepseek')
            if deepseek_config and deepseek_config.enabled:
                self._providers['deepseek-reasoner'] = DeepSeekProvider(deepseek_config)
        except Exception:
            pass

        # Try to load OpenAI o3-mini provider
        try:
            openai_config = self.config_manager.get_provider('openai')
            if openai_config and openai_config.enabled:
                self._providers['o3-mini'] = OpenAIProvider(openai_config)
        except Exception:
            pass

    def classify_task(self, task: str) -> TaskClassification:
        """Classify a task and determine reasoning requirements

        Args:
            task: Task description text

        Returns:
            TaskClassification with task type, reasoning level, and model recommendation
        """
        task_lower = task.lower()

        # Count keyword matches for each category
        math_count = sum(1 for kw in self.MATH_KEYWORDS if kw in task_lower)
        logic_count = sum(1 for kw in self.LOGIC_KEYWORDS if kw in task_lower)
        planning_count = sum(1 for kw in self.PLANNING_KEYWORDS if kw in task_lower)
        debugging_count = sum(1 for kw in self.DEBUGGING_KEYWORDS if kw in task_lower)
        coding_count = sum(1 for kw in self.CODING_KEYWORDS if kw in task_lower)

        # Determine task type
        counts = {
            TaskType.MATH: math_count,
            TaskType.LOGIC: logic_count,
            TaskType.PLANNING: planning_count,
            TaskType.DEBUGGING: debugging_count,
            TaskType.CODING: coding_count
        }

        max_count = max(counts.values())

        if max_count == 0:
            task_type = TaskType.GENERAL
            reasoning_level = ReasoningLevel.LOW
            confidence = 0.5
            keywords_found = []
        else:
            task_type = max(counts.items(), key=lambda x: x[1])[0]
            keywords_found = self._get_matching_keywords(task_lower, task_type)

            # Determine reasoning level based on keyword count and task complexity
            total_keywords = sum(counts.values())
            task_length = len(task.split())

            if total_keywords >= 3 or (total_keywords >= 2 and task_length > 20):
                reasoning_level = ReasoningLevel.HIGH
                confidence = 0.9
            elif total_keywords >= 1 or task_length > 20:
                reasoning_level = ReasoningLevel.MEDIUM
                confidence = 0.7
            else:
                reasoning_level = ReasoningLevel.LOW
                confidence = 0.6

        # Recommend model based on reasoning level and available providers
        recommended_model = self._recommend_model(reasoning_level)

        reasoning = self._generate_classification_reasoning(
            task_type, reasoning_level, keywords_found, max_count
        )

        return TaskClassification(
            task_type=task_type,
            reasoning_level=reasoning_level,
            confidence=confidence,
            keywords_found=keywords_found,
            recommended_model=recommended_model,
            reasoning=reasoning
        )

    def _get_matching_keywords(self, task_lower: str, task_type: TaskType) -> List[str]:
        """Get list of matching keywords for a task type"""
        keyword_lists = {
            TaskType.MATH: self.MATH_KEYWORDS,
            TaskType.LOGIC: self.LOGIC_KEYWORDS,
            TaskType.PLANNING: self.PLANNING_KEYWORDS,
            TaskType.DEBUGGING: self.DEBUGGING_KEYWORDS,
            TaskType.CODING: self.CODING_KEYWORDS,
            TaskType.GENERAL: []
        }

        keywords = keyword_lists.get(task_type, [])
        return [kw for kw in keywords if kw in task_lower]

    def _recommend_model(self, reasoning_level: ReasoningLevel) -> str:
        """Recommend model based on reasoning level and availability

        Priority:
        - HIGH: o3-mini (highest quality) > deepseek-reasoner (cost-effective)
        - MEDIUM/LOW: deepseek-reasoner (fast and cheap)
        """
        if reasoning_level == ReasoningLevel.HIGH:
            # Prefer o3-mini for highest quality reasoning
            if 'o3-mini' in self._providers:
                return 'o3-mini'
            elif 'deepseek-reasoner' in self._providers:
                return 'deepseek-reasoner'
        else:
            # Prefer DeepSeek for cost-effective reasoning
            if 'deepseek-reasoner' in self._providers:
                return 'deepseek-reasoner'
            elif 'o3-mini' in self._providers:
                return 'o3-mini'

        # Fallback to any available provider
        if self._providers:
            return list(self._providers.keys())[0]

        return 'claude-sonnet'  # Ultimate fallback

    def _generate_classification_reasoning(
        self,
        task_type: TaskType,
        reasoning_level: ReasoningLevel,
        keywords_found: List[str],
        keyword_count: int
    ) -> str:
        """Generate human-readable reasoning explanation"""
        if task_type == TaskType.GENERAL:
            return "Task does not contain specific reasoning keywords. Using general model."

        reasoning_parts = [
            f"Classified as {task_type.value} task (found {keyword_count} relevant keywords: {', '.join(keywords_found[:3])})",
            f"Reasoning level: {reasoning_level.value}",
        ]

        if reasoning_level == ReasoningLevel.HIGH:
            reasoning_parts.append("High complexity requires advanced reasoning capabilities.")
        elif reasoning_level == ReasoningLevel.MEDIUM:
            reasoning_parts.append("Moderate complexity benefits from reasoning-specialized models.")

        return " ".join(reasoning_parts)

    def route(
        self,
        task: str,
        messages: Optional[List[Message]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> RoutingResult:
        """Route a task to the appropriate reasoning model

        Args:
            task: Task description or prompt
            messages: Optional list of conversation messages (if None, creates from task)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            RoutingResult with classification, response, and optional CoT
        """
        # Classify the task
        classification = self.classify_task(task)

        # Prepare messages
        if messages is None:
            messages = [Message(role=MessageRole.USER, content=task)]

        # Get the provider for recommended model
        model = classification.recommended_model
        provider_name = self._get_provider_name(model)

        if model not in self._providers:
            raise ValueError(f"Recommended model {model} is not available. "
                           f"Available providers: {list(self._providers.keys())}")

        provider = self._providers[model]

        # Route to provider
        response = provider.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Extract chain-of-thought if available
        chain_of_thought = None
        if hasattr(provider, 'get_reasoning_content'):
            chain_of_thought = provider.get_reasoning_content(response.raw_response)

        return RoutingResult(
            task_classification=classification,
            response=response,
            model_used=model,
            provider_used=provider_name,
            chain_of_thought=chain_of_thought
        )

    def _get_provider_name(self, model: str) -> str:
        """Get provider name from model name"""
        if 'deepseek' in model:
            return 'deepseek'
        elif 'o3' in model or 'gpt' in model:
            return 'openai'
        elif 'gemini' in model:
            return 'gemini'
        else:
            return 'unknown'

    def get_available_models(self) -> List[str]:
        """Get list of available reasoning models"""
        return list(self._providers.keys())


def main():
    """CLI interface for reasoning router"""
    import argparse

    parser = argparse.ArgumentParser(description='Reasoning Task Router')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze and route a task')
    analyze_parser.add_argument('task', help='Task description')
    analyze_parser.add_argument('--show-cot', action='store_true',
                               help='Show chain-of-thought reasoning')
    analyze_parser.add_argument('--temperature', type=float, default=0.7,
                               help='Sampling temperature')
    analyze_parser.add_argument('--json', action='store_true',
                               help='Output as JSON')

    # Classify command
    classify_parser = subparsers.add_parser('classify', help='Classify a task without routing')
    classify_parser.add_argument('task', help='Task description')
    classify_parser.add_argument('--json', action='store_true',
                               help='Output as JSON')

    # Models command
    models_parser = subparsers.add_parser('models', help='List available reasoning models')
    models_parser.add_argument('--json', action='store_true',
                              help='Output as JSON')

    # Test command
    subparsers.add_parser('test', help='Test router with sample tasks')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    router = ReasoningRouter()

    if args.command == 'analyze':
        result = router.route(args.task, temperature=args.temperature)

        if args.json:
            import json
            output: Dict[str, Any] = {
                'classification': {
                    'task_type': result.task_classification.task_type.value,
                    'reasoning_level': result.task_classification.reasoning_level.value,
                    'confidence': result.task_classification.confidence,
                    'keywords_found': result.task_classification.keywords_found,
                    'recommended_model': result.task_classification.recommended_model,
                    'reasoning': result.task_classification.reasoning
                },
                'response': {
                    'content': result.response.content,
                    'model': result.model_used,
                    'provider': result.provider_used,
                    'cost': result.response.cost,
                    'tokens': result.response.usage.to_dict()
                }
            }
            if args.show_cot and result.chain_of_thought:
                output['chain_of_thought'] = result.chain_of_thought
            print(json.dumps(output, indent=2))
        else:
            print(f"Task Type: {result.task_classification.task_type.value}")
            print(f"Reasoning Level: {result.task_classification.reasoning_level.value}")
            print(f"Confidence: {result.task_classification.confidence:.2f}")
            print(f"Model Used: {result.model_used} ({result.provider_used})")
            print(f"Cost: ${result.response.cost:.6f}")
            print(f"\nClassification Reasoning:")
            print(f"  {result.task_classification.reasoning}")
            print(f"\nResponse:")
            print(f"  {result.response.content}")

            if args.show_cot and result.chain_of_thought:
                print(f"\nChain of Thought:")
                print(f"  {result.chain_of_thought}")

    elif args.command == 'classify':
        classification = router.classify_task(args.task)

        if args.json:
            import json
            output = {
                'task_type': classification.task_type.value,
                'reasoning_level': classification.reasoning_level.value,
                'confidence': classification.confidence,
                'keywords_found': classification.keywords_found,
                'recommended_model': classification.recommended_model,
                'reasoning': classification.reasoning
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Task Type: {classification.task_type.value}")
            print(f"Reasoning Level: {classification.reasoning_level.value}")
            print(f"Confidence: {classification.confidence:.2f}")
            print(f"Keywords Found: {', '.join(classification.keywords_found)}")
            print(f"Recommended Model: {classification.recommended_model}")
            print(f"\nReasoning:")
            print(f"  {classification.reasoning}")

    elif args.command == 'models':
        models = router.get_available_models()

        if args.json:
            import json
            print(json.dumps({'available_models': models}, indent=2))
        else:
            print("Available Reasoning Models:")
            if models:
                for model in models:
                    provider_name = router._get_provider_name(model)
                    print(f"  - {model} ({provider_name})")
            else:
                print("  No reasoning models configured")

    elif args.command == 'test':
        test_tasks = [
            "Solve the equation: 2x^2 + 5x - 3 = 0",
            "Write a function to reverse a linked list",
            "Explain why this code produces a null pointer exception",
            "Design a system architecture for a distributed cache",
            "What is the capital of France?"
        ]

        print("Testing reasoning router with sample tasks:\n")
        for i, task in enumerate(test_tasks, 1):
            classification = router.classify_task(task)
            print(f"{i}. Task: {task}")
            print(f"   Type: {classification.task_type.value}")
            print(f"   Level: {classification.reasoning_level.value}")
            print(f"   Model: {classification.recommended_model}")
            print()


if __name__ == '__main__':
    main()
