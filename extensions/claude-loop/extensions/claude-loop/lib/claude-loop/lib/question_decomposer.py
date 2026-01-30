#!/usr/bin/env python3
"""
Question Decomposer - Breaks complex research questions into 3-7 sub-questions

This module analyzes a research question and decomposes it into focused sub-questions
that can be delegated to specialist agents.
"""

import re
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class SubQuestion:
    """Represents a decomposed sub-question"""
    id: str
    question: str
    type: str  # academic, technical, market, general
    reasoning: str  # Why this sub-question is important


class QuestionDecomposer:
    """Decomposes research questions into sub-questions"""

    # Keywords that indicate question type
    ACADEMIC_KEYWORDS = [
        'research', 'paper', 'study', 'theory', 'model', 'algorithm',
        'scientific', 'academic', 'published', 'peer-reviewed', 'arxiv'
    ]

    TECHNICAL_KEYWORDS = [
        'implementation', 'implement', 'code', 'api', 'library', 'framework', 'tool',
        'github', 'documentation', 'how to', 'tutorial', 'example', 'build', 'create'
    ]

    MARKET_KEYWORDS = [
        'market', 'company', 'business', 'pricing', 'competitor', 'revenue',
        'investment', 'invest', 'stock', 'crypto', 'valuation', 'trend',
        'bitcoin', 'ethereum', 'trading', 'portfolio'
    ]

    def __init__(self):
        """Initialize the question decomposer"""
        pass

    def decompose(self, question: str, min_questions: int = 3, max_questions: int = 7) -> List[SubQuestion]:
        """
        Decompose a complex question into 3-7 sub-questions.

        Args:
            question: The main research question
            min_questions: Minimum number of sub-questions (default: 3)
            max_questions: Maximum number of sub-questions (default: 7)

        Returns:
            List of SubQuestion objects

        Raises:
            ValueError: If question is too short or invalid
        """
        if not question or len(question.strip()) < 10:
            raise ValueError("Question must be at least 10 characters long")

        # Normalize question
        question = question.strip()

        # Extract key aspects
        aspects = self._extract_aspects(question)

        # Generate sub-questions
        sub_questions = []

        # 1. Definition/Background sub-question (if needed)
        if self._needs_definition(question):
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=self._generate_definition_question(question),
                type=self._classify_question_type(question, prefer='academic'),
                reasoning="Understanding key concepts and definitions"
            ))

        # 2. Current State sub-question
        sub_questions.append(SubQuestion(
            id=f"SQ-{len(sub_questions)+1:03d}",
            question=self._generate_current_state_question(question),
            type=self._classify_question_type(question),
            reasoning="Understanding the current state and recent developments"
        ))

        # 3. Technical Details (if technical question)
        if self._is_technical(question):
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=self._generate_technical_question(question),
                type='technical',
                reasoning="Understanding implementation and technical details"
            ))

        # 4. Market/Business Context (if market question)
        if self._is_market(question):
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=self._generate_market_question(question),
                type='market',
                reasoning="Understanding market dynamics and business context"
            ))

        # 5. Comparisons (if comparative question or multiple entities)
        if self._needs_comparison(question):
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=self._generate_comparison_question(question),
                type=self._classify_question_type(question),
                reasoning="Comparing different approaches or alternatives"
            ))

        # 6. Challenges/Limitations
        sub_questions.append(SubQuestion(
            id=f"SQ-{len(sub_questions)+1:03d}",
            question=self._generate_challenges_question(question),
            type=self._classify_question_type(question),
            reasoning="Understanding limitations and challenges"
        ))

        # 7. Future/Trends (if we still need more questions)
        if len(sub_questions) < min_questions:
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=self._generate_future_question(question),
                type=self._classify_question_type(question),
                reasoning="Understanding future directions and trends"
            ))

        # Ensure we're within bounds
        if len(sub_questions) < min_questions:
            # Add general exploration question
            sub_questions.append(SubQuestion(
                id=f"SQ-{len(sub_questions)+1:03d}",
                question=f"What are the key considerations for {self._extract_main_topic(question)}?",
                type='general',
                reasoning="General exploration of key considerations"
            ))

        if len(sub_questions) > max_questions:
            # Prioritize and trim
            sub_questions = sub_questions[:max_questions]

        return sub_questions

    def _extract_aspects(self, question: str) -> List[str]:
        """Extract key aspects from the question"""
        # Simple word extraction (can be enhanced)
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)
        return words

    def _extract_main_topic(self, question: str) -> str:
        """Extract the main topic from the question"""
        # Remove question words
        topic = re.sub(r'^(what|how|why|when|where|which|who)\s+(is|are|do|does|did|can|could|would|should)\s+', '', question.lower())
        topic = re.sub(r'\?$', '', topic).strip()
        return topic

    def _needs_definition(self, question: str) -> bool:
        """Check if the question needs a definition sub-question"""
        definition_indicators = ['what is', 'what are', 'define', 'explain']
        question_lower = question.lower()
        return any(indicator in question_lower for indicator in definition_indicators)

    def _is_technical(self, question: str) -> bool:
        """Check if question is technical in nature"""
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in self.TECHNICAL_KEYWORDS)

    def _is_market(self, question: str) -> bool:
        """Check if question is market-related"""
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in self.MARKET_KEYWORDS)

    def _needs_comparison(self, question: str) -> bool:
        """Check if question involves comparison"""
        comparison_words = ['compare', 'versus', 'vs', 'difference', 'better', 'best', 'alternative']
        question_lower = question.lower()
        return any(word in question_lower for word in comparison_words) or ' and ' in question_lower

    def _classify_question_type(self, question: str, prefer: str = None) -> str:
        """
        Classify the question type based on keywords.

        Args:
            question: The question text
            prefer: Preferred type to return if no clear match

        Returns:
            Type: 'academic', 'technical', 'market', or 'general'
        """
        question_lower = question.lower()

        if prefer:
            return prefer

        # Count keyword matches for each type
        academic_score = sum(1 for kw in self.ACADEMIC_KEYWORDS if kw in question_lower)
        technical_score = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in question_lower)
        market_score = sum(1 for kw in self.MARKET_KEYWORDS if kw in question_lower)

        scores = {
            'academic': academic_score,
            'technical': technical_score,
            'market': market_score
        }

        max_score = max(scores.values())
        if max_score == 0:
            return 'general'

        return max(scores, key=scores.get)

    def _generate_definition_question(self, question: str) -> str:
        """Generate a definition sub-question"""
        topic = self._extract_main_topic(question)
        return f"What are the key concepts and definitions related to {topic}?"

    def _generate_current_state_question(self, question: str) -> str:
        """Generate a current state sub-question"""
        topic = self._extract_main_topic(question)
        return f"What is the current state of {topic}?"

    def _generate_technical_question(self, question: str) -> str:
        """Generate a technical sub-question"""
        topic = self._extract_main_topic(question)
        return f"How is {topic} implemented technically?"

    def _generate_market_question(self, question: str) -> str:
        """Generate a market sub-question"""
        topic = self._extract_main_topic(question)
        return f"What is the market landscape for {topic}?"

    def _generate_comparison_question(self, question: str) -> str:
        """Generate a comparison sub-question"""
        topic = self._extract_main_topic(question)
        return f"How do different approaches to {topic} compare?"

    def _generate_challenges_question(self, question: str) -> str:
        """Generate a challenges sub-question"""
        topic = self._extract_main_topic(question)
        return f"What are the main challenges and limitations with {topic}?"

    def _generate_future_question(self, question: str) -> str:
        """Generate a future trends sub-question"""
        topic = self._extract_main_topic(question)
        return f"What are the future trends and directions for {topic}?"


def main():
    """Test the question decomposer"""
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python3 question-decomposer.py 'Your research question'")
        sys.exit(1)

    question = ' '.join(sys.argv[1:])
    decomposer = QuestionDecomposer()

    try:
        sub_questions = decomposer.decompose(question)
        result = {
            'mainQuestion': question,
            'subQuestions': [
                {
                    'id': sq.id,
                    'question': sq.question,
                    'type': sq.type,
                    'reasoning': sq.reasoning
                }
                for sq in sub_questions
            ]
        }
        print(json.dumps(result, indent=2))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
