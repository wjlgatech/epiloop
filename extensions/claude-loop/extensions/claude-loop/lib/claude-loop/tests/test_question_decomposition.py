#!/usr/bin/env python3
"""
Tests for question decomposition functionality (US-001)

Tests that question-decomposer.py correctly breaks complex questions
into 3-7 sub-questions and assigns appropriate types.
"""

import sys
import os
from pathlib import Path

# Add lib directory to path
LIB_DIR = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(LIB_DIR))

from question_decomposer import QuestionDecomposer, SubQuestion


def test_simple_ai_question():
    """Test decomposition of a simple AI-related question"""
    decomposer = QuestionDecomposer()
    question = "What are the latest advances in AI reasoning models?"

    sub_questions = decomposer.decompose(question)

    # Should generate 3-7 sub-questions
    assert 3 <= len(sub_questions) <= 7, f"Expected 3-7 sub-questions, got {len(sub_questions)}"

    # All should have required fields
    for sq in sub_questions:
        assert sq.id, "Sub-question must have an ID"
        assert sq.question, "Sub-question must have a question"
        assert sq.type in ['academic', 'technical', 'market', 'general'], f"Invalid type: {sq.type}"
        assert sq.reasoning, "Sub-question must have reasoning"

    # At least one should be academic (since it's an AI research question)
    types = [sq.type for sq in sub_questions]
    assert 'academic' in types or 'technical' in types, "Expected academic or technical sub-questions for AI question"

    print("✓ test_simple_ai_question passed")
    return True


def test_market_question():
    """Test decomposition of a market-related question"""
    decomposer = QuestionDecomposer()
    question = "Should I invest in Bitcoin or Ethereum?"

    sub_questions = decomposer.decompose(question)

    # Should generate 3-7 sub-questions
    assert 3 <= len(sub_questions) <= 7, f"Expected 3-7 sub-questions, got {len(sub_questions)}"

    # At least one should be market type
    types = [sq.type for sq in sub_questions]
    assert 'market' in types, "Expected market sub-questions for investment question"

    print("✓ test_market_question passed")
    return True


def test_technical_question():
    """Test decomposition of a technical question"""
    decomposer = QuestionDecomposer()
    question = "How do I implement OAuth authentication with Google?"

    sub_questions = decomposer.decompose(question)

    # Should generate 3-7 sub-questions
    assert 3 <= len(sub_questions) <= 7, f"Expected 3-7 sub-questions, got {len(sub_questions)}"

    # At least one should be technical type
    types = [sq.type for sq in sub_questions]
    assert 'technical' in types, "Expected technical sub-questions for implementation question"

    print("✓ test_technical_question passed")
    return True


def test_comparison_question():
    """Test decomposition of a comparison question"""
    decomposer = QuestionDecomposer()
    question = "Compare GPT-4 and Claude Opus for code generation"

    sub_questions = decomposer.decompose(question)

    # Should generate 3-7 sub-questions
    assert 3 <= len(sub_questions) <= 7, f"Expected 3-7 sub-questions, got {len(sub_questions)}"

    # Should include comparison-related sub-question
    questions_text = ' '.join([sq.question for sq in sub_questions]).lower()
    assert 'compare' in questions_text or 'different' in questions_text, \
        "Expected comparison sub-question for comparative question"

    print("✓ test_comparison_question passed")
    return True


def test_invalid_question():
    """Test that invalid questions raise ValueError"""
    decomposer = QuestionDecomposer()

    # Too short
    try:
        decomposer.decompose("hi")
        assert False, "Should raise ValueError for short question"
    except ValueError:
        pass

    # Empty
    try:
        decomposer.decompose("")
        assert False, "Should raise ValueError for empty question"
    except ValueError:
        pass

    print("✓ test_invalid_question passed")
    return True


def test_sub_question_ids():
    """Test that sub-question IDs are sequential and formatted correctly"""
    decomposer = QuestionDecomposer()
    question = "What is machine learning?"

    sub_questions = decomposer.decompose(question)

    # Check ID format
    for i, sq in enumerate(sub_questions):
        expected_id = f"SQ-{i+1:03d}"
        assert sq.id == expected_id, f"Expected ID {expected_id}, got {sq.id}"

    print("✓ test_sub_question_ids passed")
    return True


def run_all_tests():
    """Run all tests"""
    tests = [
        test_simple_ai_question,
        test_market_question,
        test_technical_question,
        test_comparison_question,
        test_invalid_question,
        test_sub_question_ids
    ]

    print("Running question decomposition tests...")
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
