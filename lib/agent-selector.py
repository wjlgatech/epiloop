#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/agent-selector.py - Intelligent Agent Selection for Research Loop

Automatically selects the most appropriate research agent(s) based on question
analysis, keywords, and domain detection. Supports multi-agent selection for
complex questions that span multiple domains.

Available Agents:
    academic-scanner  - Academic papers, research, citations
    technical-diver   - Code, documentation, tutorials, APIs
    market-analyst    - Companies, pricing, competitive intelligence

Features:
- Keyword-based domain classification
- Multi-agent selection for cross-domain questions
- Confidence scoring for agent relevance
- Detailed reasoning in verbose mode
- Support for forced agent override

Usage:
    python3 lib/agent-selector.py select "your research question"
    python3 lib/agent-selector.py select "question" --json
    python3 lib/agent-selector.py select "question" --verbose
    python3 lib/agent-selector.py select "question" --force academic-scanner
    python3 lib/agent-selector.py list

Examples:
    # Academic question
    python3 lib/agent-selector.py select "What are the latest papers on transformer architectures?"

    # Technical question
    python3 lib/agent-selector.py select "How do I implement OAuth2 in FastAPI?"

    # Market question
    python3 lib/agent-selector.py select "What is Anthropic's funding history and competitors?"

    # Multi-domain question
    python3 lib/agent-selector.py select "What ML papers influenced OpenAI's pricing strategy?"
"""

import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Agent(Enum):
    """Available research agents."""
    ACADEMIC_SCANNER = "academic-scanner"
    TECHNICAL_DIVER = "technical-diver"
    MARKET_ANALYST = "market-analyst"

    @property
    def description(self) -> str:
        """Return agent description."""
        descriptions = {
            Agent.ACADEMIC_SCANNER: "Academic papers, research publications, citations, scientific literature",
            Agent.TECHNICAL_DIVER: "Code examples, documentation, tutorials, APIs, Stack Overflow",
            Agent.MARKET_ANALYST: "Company info, pricing, competitive analysis, market intelligence",
        }
        return descriptions[self]

    @property
    def file_path(self) -> str:
        """Return path to agent spec file."""
        return f"agents/{self.value}.md"


# ============================================================================
# Keyword Definitions
# ============================================================================

# Keywords strongly indicating academic research needs
ACADEMIC_KEYWORDS = {
    # Research terms
    "paper", "papers", "research", "study", "studies", "publication",
    "publications", "journal", "journals", "conference", "proceedings",
    "preprint", "preprints", "arxiv", "scholar", "scholarly",
    # Academic verbs
    "published", "cited", "citations", "peer-reviewed", "peer reviewed",
    # Research methodology
    "methodology", "empirical", "theoretical", "experiment", "experiments",
    "hypothesis", "findings", "results", "analysis", "literature review",
    # Academic entities
    "authors", "researchers", "scientists", "professors", "university",
    "universities", "lab", "laboratory", "institute",
    # Publication types
    "survey", "meta-analysis", "systematic review", "thesis", "dissertation",
    # Domain-specific academic
    "algorithm", "theorem", "proof", "model", "neural network", "deep learning",
    "machine learning", "nlp", "computer vision", "reinforcement learning",
}

# Keywords strongly indicating technical documentation needs
TECHNICAL_KEYWORDS = {
    # Development terms
    "code", "coding", "programming", "implement", "implementation",
    "developer", "development", "software", "engineering",
    # Documentation
    "documentation", "docs", "tutorial", "tutorials", "guide", "guides",
    "example", "examples", "snippet", "snippets", "reference",
    # Technical resources
    "github", "stackoverflow", "stack overflow", "npm", "pip", "pypi",
    "package", "library", "framework", "sdk", "api", "apis",
    # Technical actions
    "install", "setup", "configure", "deploy", "debug", "debugging",
    "error", "exception", "fix", "solve", "troubleshoot",
    # Languages and tools
    "python", "javascript", "typescript", "java", "rust", "go", "golang",
    "react", "vue", "angular", "node", "express", "fastapi", "django",
    "docker", "kubernetes", "aws", "gcp", "azure",
    # Technical concepts
    "function", "class", "method", "variable", "database", "sql",
    "rest", "graphql", "authentication", "oauth", "jwt",
}

# Keywords strongly indicating market/business research needs
MARKET_KEYWORDS = {
    # Business terms
    "company", "companies", "startup", "startups", "enterprise", "business",
    "corporation", "firm", "firms", "organization",
    # Financial terms
    "funding", "funded", "investment", "investors", "valuation", "revenue",
    "profit", "pricing", "price", "prices", "cost", "costs", "subscription",
    "series a", "series b", "series c", "seed", "ipo",
    # Market terms
    "market", "markets", "industry", "industries", "sector", "sectors",
    "competition", "competitor", "competitors", "competitive", "landscape",
    # Analysis terms
    "analysis", "benchmark", "comparison", "versus", "vs", "alternative",
    "alternatives", "leader", "leaders", "share",
    # Business intelligence
    "customers", "users", "growth", "trends", "forecast", "projection",
    "strategy", "positioning", "segment", "segments",
    # Company-specific
    "ceo", "founder", "founders", "employee", "employees", "headcount",
    "headquarter", "headquarters", "founded", "acquisition", "merger",
}

# Question patterns for additional classification
QUESTION_PATTERNS = {
    Agent.ACADEMIC_SCANNER: [
        r"what (papers|research|studies) (on|about|regarding)",
        r"(latest|recent|new) (papers|research|publications)",
        r"(literature|systematic) review",
        r"(cited|citations) (by|for|in)",
        r"(state of the art|sota) (in|for|on)",
        r"academic (papers|research|literature)",
        r"peer[- ]reviewed",
    ],
    Agent.TECHNICAL_DIVER: [
        r"how (do i|to|can i) (implement|code|build|create|setup|configure)",
        r"(code|programming) (example|snippet|sample)",
        r"(error|exception|bug).*(fix|solve|resolve)",
        r"(best practice|pattern)s? for",
        r"(documentation|docs|tutorial) for",
        r"(install|setup|configure) .*(package|library|tool)",
        r"(api|sdk) (reference|documentation|usage)",
    ],
    Agent.MARKET_ANALYST: [
        r"(funding|valuation|revenue) (of|for|history)",
        r"(competitor|competitive|competition) (analysis|landscape|of)",
        r"(pricing|price|cost) (of|for|comparison)",
        r"(market|industry) (size|share|analysis|trends)",
        r"(company|startup) (profile|overview|information)",
        r"(who|what) (competes|competitors) (with|of|for)",
        r"(business model|monetization) of",
    ],
}


@dataclass
class AgentScore:
    """Score and reasoning for a single agent."""
    agent: Agent
    score: float
    keyword_matches: list[str] = field(default_factory=list)
    pattern_matches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent": self.agent.value,
            "score": round(self.score, 3),
            "keyword_matches": self.keyword_matches,
            "pattern_matches": self.pattern_matches,
        }


@dataclass
class SelectionResult:
    """Result of agent selection."""
    question: str
    primary_agent: Agent
    primary_score: float
    all_agents: list[AgentScore]
    is_multi_agent: bool
    reasoning: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question": self.question,
            "primary_agent": self.primary_agent.value,
            "primary_score": round(self.primary_score, 3),
            "all_agents": [a.to_dict() for a in self.all_agents],
            "is_multi_agent": self.is_multi_agent,
            "selected_agents": [
                a.agent.value for a in self.all_agents
                if a.score >= 0.3  # Include agents with meaningful scores
            ],
            "reasoning": self.reasoning,
        }

    def get_selected_agents(self, threshold: float = 0.3) -> list[Agent]:
        """Get list of agents above the selection threshold."""
        return [a.agent for a in self.all_agents if a.score >= threshold]


class AgentSelector:
    """Selects appropriate research agent(s) based on question analysis."""

    def __init__(self, verbose: bool = False):
        """
        Initialize agent selector.

        Args:
            verbose: If True, include detailed reasoning
        """
        self.verbose = verbose
        self.agents = list(Agent)

    def select(self, question: str, force_agent: Optional[str] = None) -> SelectionResult:
        """
        Select the most appropriate agent(s) for a question.

        Args:
            question: The research question to analyze
            force_agent: Optional agent name to force selection

        Returns:
            SelectionResult with selected agent(s) and reasoning
        """
        question_lower = question.lower()
        reasoning = []

        # Handle forced agent selection
        if force_agent:
            try:
                agent = Agent(force_agent)
                reasoning.append(f"Forced selection: {force_agent}")
                return SelectionResult(
                    question=question,
                    primary_agent=agent,
                    primary_score=1.0,
                    all_agents=[AgentScore(agent=agent, score=1.0)],
                    is_multi_agent=False,
                    reasoning=reasoning,
                )
            except ValueError:
                raise ValueError(f"Unknown agent: {force_agent}. Valid agents: {[a.value for a in Agent]}")

        # Score each agent
        scores: list[AgentScore] = []

        for agent in self.agents:
            agent_score = self._score_agent(agent, question_lower)
            scores.append(agent_score)

            if self.verbose and agent_score.score > 0:
                reasoning.append(
                    f"{agent.value}: score={agent_score.score:.2f}, "
                    f"keywords={len(agent_score.keyword_matches)}, "
                    f"patterns={len(agent_score.pattern_matches)}"
                )

        # Sort by score descending
        scores.sort(key=lambda x: x.score, reverse=True)

        # Determine if multi-agent is needed
        primary = scores[0]
        secondary = scores[1] if len(scores) > 1 else None

        # Multi-agent threshold: secondary agent has at least 50% of primary score
        # and primary score is not dominant (< 0.7)
        is_multi_agent = (
            secondary is not None and
            secondary.score >= 0.3 and
            secondary.score >= primary.score * 0.5 and
            primary.score < 0.7
        )

        if is_multi_agent:
            reasoning.append(
                f"Multi-agent selection: {primary.agent.value} (primary) and "
                f"{secondary.agent.value} (secondary) - question spans multiple domains"
            )
        else:
            reasoning.append(f"Single agent selection: {primary.agent.value}")

        # Add domain explanation
        if primary.keyword_matches:
            reasoning.append(f"Key indicators: {', '.join(primary.keyword_matches[:5])}")

        return SelectionResult(
            question=question,
            primary_agent=primary.agent,
            primary_score=primary.score,
            all_agents=scores,
            is_multi_agent=is_multi_agent,
            reasoning=reasoning,
        )

    def _score_agent(self, agent: Agent, question_lower: str) -> AgentScore:
        """
        Score how well an agent matches a question.

        Args:
            agent: The agent to score
            question_lower: Lowercase question text

        Returns:
            AgentScore with score and match details
        """
        # Get keyword set for this agent
        keyword_set = self._get_keywords(agent)

        # Find keyword matches
        keyword_matches = []
        for keyword in keyword_set:
            # Use word boundary matching for multi-word keywords
            if " " in keyword:
                if keyword in question_lower:
                    keyword_matches.append(keyword)
            else:
                # Single word: check word boundaries
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, question_lower):
                    keyword_matches.append(keyword)

        # Find pattern matches
        pattern_matches = []
        patterns = QUESTION_PATTERNS.get(agent, [])
        for pattern in patterns:
            if re.search(pattern, question_lower):
                pattern_matches.append(pattern)

        # Calculate score
        # Base: keyword density (number of matches / sqrt of keyword set size)
        keyword_score = len(keyword_matches) / (len(keyword_set) ** 0.5) if keyword_set else 0
        keyword_score = min(keyword_score, 0.5)  # Cap at 0.5

        # Pattern bonus: each pattern match adds significant weight
        pattern_score = min(len(pattern_matches) * 0.2, 0.4)  # Cap at 0.4

        # Combine scores
        total_score = min(keyword_score + pattern_score, 1.0)

        # Apply minimum threshold - if no matches, score is 0
        if not keyword_matches and not pattern_matches:
            total_score = 0.1  # Small baseline for fallback

        return AgentScore(
            agent=agent,
            score=total_score,
            keyword_matches=keyword_matches,
            pattern_matches=pattern_matches,
        )

    def _get_keywords(self, agent: Agent) -> set[str]:
        """Get keyword set for an agent."""
        keyword_map = {
            Agent.ACADEMIC_SCANNER: ACADEMIC_KEYWORDS,
            Agent.TECHNICAL_DIVER: TECHNICAL_KEYWORDS,
            Agent.MARKET_ANALYST: MARKET_KEYWORDS,
        }
        return keyword_map.get(agent, set())


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_select(question: str, force: Optional[str], json_output: bool, verbose: bool) -> int:
    """Select agent(s) for a question."""
    selector = AgentSelector(verbose=verbose)

    try:
        result = selector.select(question, force_agent=force)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Question: {result.question}")
        print()
        print(f"Primary Agent: {result.primary_agent.value}")
        print(f"Confidence: {result.primary_score:.0%}")
        print(f"Agent Description: {result.primary_agent.description}")
        print()

        if result.is_multi_agent:
            selected = result.get_selected_agents()
            print(f"Multi-Agent Mode: Yes")
            print(f"Selected Agents: {', '.join(a.value for a in selected)}")
            print()

        print("All Agent Scores:")
        for agent_score in result.all_agents:
            marker = " <-- selected" if agent_score.score >= 0.3 else ""
            print(f"  {agent_score.agent.value}: {agent_score.score:.0%}{marker}")

        if verbose:
            print()
            print("Reasoning:")
            for reason in result.reasoning:
                print(f"  - {reason}")

            print()
            print("Keyword Matches:")
            for agent_score in result.all_agents:
                if agent_score.keyword_matches:
                    print(f"  {agent_score.agent.value}: {', '.join(agent_score.keyword_matches[:10])}")

    return 0


def cmd_list(json_output: bool) -> int:
    """List available agents."""
    agents_data = [
        {
            "name": agent.value,
            "description": agent.description,
            "file_path": agent.file_path,
        }
        for agent in Agent
    ]

    if json_output:
        print(json.dumps({"agents": agents_data}, indent=2))
    else:
        print("Available Research Agents:")
        print("=" * 60)
        for agent in Agent:
            print(f"\n{agent.value}")
            print(f"  Description: {agent.description}")
            print(f"  Spec File: {agent.file_path}")

    return 0


def cmd_test(json_output: bool) -> int:
    """Run test questions to demonstrate agent selection."""
    test_questions = [
        # Academic
        "What are the latest papers on transformer architectures for NLP?",
        "Find research on reinforcement learning from human feedback",
        "What studies have been published about GPT-4's capabilities?",

        # Technical
        "How do I implement OAuth2 authentication in FastAPI?",
        "What's the best way to handle errors in async Python code?",
        "Show me code examples for React hooks with TypeScript",

        # Market
        "What is OpenAI's current valuation and funding history?",
        "Who are the main competitors to Anthropic?",
        "What is the pricing structure for AWS Lambda?",

        # Multi-domain
        "What papers influenced OpenAI's API pricing decisions?",
        "How do companies like Hugging Face implement their ML inference APIs?",
        "Research on LLM deployment costs and optimization techniques",
    ]

    selector = AgentSelector(verbose=False)
    results = []

    for question in test_questions:
        result = selector.select(question)
        results.append({
            "question": question,
            "primary_agent": result.primary_agent.value,
            "score": result.primary_score,
            "multi_agent": result.is_multi_agent,
            "selected": [a.value for a in result.get_selected_agents()],
        })

    if json_output:
        print(json.dumps({"test_results": results}, indent=2))
    else:
        print("Agent Selection Test Results")
        print("=" * 80)
        for r in results:
            multi = " [MULTI]" if r["multi_agent"] else ""
            print(f"\nQ: {r['question'][:60]}...")
            print(f"   -> {r['primary_agent']} ({r['score']:.0%}){multi}")
            if r["multi_agent"]:
                print(f"      All selected: {', '.join(r['selected'])}")

    return 0


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Intelligent Agent Selection for Research Loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s select "What papers discuss transformer architectures?"
  %(prog)s select "How to implement OAuth in Python?" --verbose
  %(prog)s select "What is Anthropic's valuation?" --json
  %(prog)s select "question" --force academic-scanner
  %(prog)s list
  %(prog)s test
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # select command
    select_parser = subparsers.add_parser("select", help="Select agent(s) for a question")
    select_parser.add_argument("question", help="The research question to analyze")
    select_parser.add_argument("--json", action="store_true", help="Output as JSON")
    select_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output with reasoning")
    select_parser.add_argument("--force", help="Force selection of specific agent")

    # list command
    list_parser = subparsers.add_parser("list", help="List available agents")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # test command
    test_parser = subparsers.add_parser("test", help="Run test questions")
    test_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "select":
        return cmd_select(args.question, args.force, args.json, args.verbose)
    elif args.command == "list":
        return cmd_list(args.json)
    elif args.command == "test":
        return cmd_test(args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
