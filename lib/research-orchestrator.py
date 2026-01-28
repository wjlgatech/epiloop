#!/usr/bin/env python3
"""
Research Orchestrator - Main orchestration logic for research-loop

This module coordinates the research process:
1. Decompose research question into sub-questions
2. Delegate sub-questions to specialist agents
3. Manage research state
4. Coordinate findings collection
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add lib directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from question_decomposer import QuestionDecomposer, SubQuestion


class ResearchOrchestrator:
    """Orchestrates the research loop process"""

    # Agent type mapping for sub-question types
    AGENT_MAPPING = {
        'academic': 'academic-scanner',
        'technical': 'technical-diver',
        'market': 'market-analyst',
        'general': 'lead-researcher'
    }

    def __init__(self, state_file: str):
        """
        Initialize the research orchestrator.

        Args:
            state_file: Path to research state JSON file
        """
        self.state_file = Path(state_file)
        self.state: Optional[Dict] = None
        self.decomposer = QuestionDecomposer()

    def initialize_research(self, question: str) -> Dict:
        """
        Initialize a new research session.

        Args:
            question: The main research question

        Returns:
            Initial research state dictionary

        Raises:
            ValueError: If question is invalid
        """
        # Decompose question
        print(f"Decomposing research question into sub-questions...")
        sub_questions = self.decomposer.decompose(question)

        # Generate research ID
        research_id = self._generate_research_id()

        # Create initial state
        state = {
            'researchId': research_id,
            'question': question,
            'status': 'decomposing',
            'createdAt': datetime.utcnow().isoformat() + 'Z',
            'subQuestions': [],
            'metadata': {
                'totalSources': 0,
                'domain': self._detect_domain(question),
                'notes': ''
            }
        }

        # Add sub-questions with agent assignments
        for sq in sub_questions:
            sub_question_data = {
                'id': sq.id,
                'question': sq.question,
                'type': sq.type,
                'status': 'pending',
                'assignedAgent': self.AGENT_MAPPING.get(sq.type, 'lead-researcher'),
                'findings': [],
                'confidence': 0
            }
            state['subQuestions'].append(sub_question_data)

        # Update status
        state['status'] = 'researching'

        self.state = state
        return state

    def load_state(self) -> Dict:
        """
        Load existing research state from file.

        Returns:
            Research state dictionary

        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If state file is invalid JSON
        """
        if not self.state_file.exists():
            raise FileNotFoundError(f"Research state file not found: {self.state_file}")

        with open(self.state_file, 'r') as f:
            self.state = json.load(f)

        return self.state

    def save_state(self):
        """Save current research state to file"""
        if self.state is None:
            raise ValueError("No state to save")

        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Write state
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def delegate_sub_questions(self):
        """
        Delegate sub-questions to appropriate agents.

        This method assigns each sub-question to the appropriate specialist agent
        based on the question type.
        """
        if self.state is None:
            raise ValueError("No research state loaded")

        print(f"\nDelegating {len(self.state['subQuestions'])} sub-questions to specialist agents:")
        print()

        for sq in self.state['subQuestions']:
            agent = sq['assignedAgent']
            print(f"  [{sq['id']}] {sq['question']}")
            print(f"    → Agent: {agent} (type: {sq['type']})")
            print()

        # In the current implementation, we just show the delegation
        # Future stories will implement actual agent execution
        print("Note: Agent execution will be implemented in future stories (US-002, US-003, US-004)")

    def run(self, question: Optional[str] = None, resume: bool = False):
        """
        Run the research orchestrator.

        Args:
            question: Research question (required if not resuming)
            resume: Resume from existing state

        Raises:
            ValueError: If parameters are invalid
        """
        if resume:
            # Load existing state
            print(f"Loading research state from: {self.state_file}")
            self.load_state()
            print(f"Resumed research: {self.state['researchId']}")
            print(f"Question: {self.state['question']}")
            print(f"Status: {self.state['status']}")
        else:
            # Initialize new research
            if not question:
                raise ValueError("Research question required when not resuming")

            print(f"Initializing new research session...")
            self.initialize_research(question)
            print(f"Research ID: {self.state['researchId']}")
            print(f"Generated {len(self.state['subQuestions'])} sub-questions")

        # Delegate sub-questions
        self.delegate_sub_questions()

        # Save state
        print(f"\nSaving research state to: {self.state_file}")
        self.save_state()

        print(f"\nResearch orchestration complete!")
        print(f"Current status: {self.state['status']}")

    def _generate_research_id(self) -> str:
        """
        Generate a unique research ID.

        Returns:
            Research ID in format RES-XXX
        """
        # Simple sequential ID (can be enhanced)
        # For now, use timestamp-based ID
        timestamp = datetime.utcnow().strftime('%H%M%S')
        return f"RES-{timestamp[-3:]}"

    def _detect_domain(self, question: str) -> str:
        """
        Detect the research domain from the question.

        Args:
            question: Research question

        Returns:
            Domain name (ai-ml, investment, general, etc.)
        """
        question_lower = question.lower()

        # AI/ML domain
        ai_ml_keywords = ['ai', 'ml', 'machine learning', 'deep learning', 'neural', 'model', 'llm', 'gpt', 'claude']
        if any(kw in question_lower for kw in ai_ml_keywords):
            return 'ai-ml'

        # Investment domain
        investment_keywords = ['stock', 'crypto', 'investment', 'trading', 'portfolio', 'bitcoin', 'ethereum']
        if any(kw in question_lower for kw in investment_keywords):
            return 'investment'

        return 'general'


def main():
    """Main entry point for research orchestrator"""
    parser = argparse.ArgumentParser(description='Research Loop Orchestrator')
    parser.add_argument('--state', required=True, help='Path to research state file')
    parser.add_argument('--question', help='Research question')
    parser.add_argument('--resume', action='store_true', help='Resume from existing state')

    args = parser.parse_args()

    # Validate arguments
    if not args.resume and not args.question:
        parser.error('--question is required when not using --resume')

    if args.resume and args.question:
        parser.error('Cannot specify both --question and --resume')

    # Run orchestrator
    try:
        orchestrator = ResearchOrchestrator(args.state)
        orchestrator.run(question=args.question, resume=args.resume)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
