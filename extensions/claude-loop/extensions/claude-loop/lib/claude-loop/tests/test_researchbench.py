"""
Tests for ResearchBench Dataset Integrity and Evaluator Functionality

This test suite verifies:
1. Dataset integrity (all questions have required fields)
2. Ground truth file validity
3. Evaluator function correctness
4. Cross-reference consistency

Run with: pytest tests/test_researchbench.py -v
"""

import pytest
import json
import os
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.researchbench_evaluator import (
    ResearchBenchEvaluator,
    EvaluationResult,
    BenchmarkReport,
    evaluate_decomposition,
    evaluate_source_coverage,
    evaluate_synthesis
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def evaluator():
    """Create evaluator instance for tests."""
    return ResearchBenchEvaluator()


@pytest.fixture
def data_dir():
    """Get the data directory path."""
    return Path(__file__).parent.parent / "data" / "researchbench"


@pytest.fixture
def questions(data_dir):
    """Load questions from dataset."""
    with open(data_dir / "questions.json", 'r') as f:
        return json.load(f)


@pytest.fixture
def ground_truth_files(data_dir):
    """Get list of ground truth files."""
    gt_dir = data_dir / "ground_truth"
    if gt_dir.exists():
        return list(gt_dir.glob("*.json"))
    return []


# ============================================================================
# Dataset Structure Tests
# ============================================================================

class TestDatasetStructure:
    """Tests for basic dataset file structure."""

    def test_questions_file_exists(self, data_dir):
        """Verify questions.json exists."""
        questions_file = data_dir / "questions.json"
        assert questions_file.exists(), "questions.json file not found"

    def test_questions_file_valid_json(self, data_dir):
        """Verify questions.json is valid JSON."""
        questions_file = data_dir / "questions.json"
        try:
            with open(questions_file, 'r') as f:
                data = json.load(f)
            assert isinstance(data, list), "questions.json should contain a list"
        except json.JSONDecodeError as e:
            pytest.fail(f"questions.json is not valid JSON: {e}")

    def test_ground_truth_directory_exists(self, data_dir):
        """Verify ground_truth directory exists."""
        gt_dir = data_dir / "ground_truth"
        assert gt_dir.exists(), "ground_truth directory not found"

    def test_ground_truth_files_valid_json(self, ground_truth_files):
        """Verify all ground truth files are valid JSON."""
        for gt_file in ground_truth_files:
            try:
                with open(gt_file, 'r') as f:
                    data = json.load(f)
                assert isinstance(data, dict), f"{gt_file.name} should contain a dict"
            except json.JSONDecodeError as e:
                pytest.fail(f"{gt_file.name} is not valid JSON: {e}")


# ============================================================================
# Question Integrity Tests
# ============================================================================

class TestQuestionIntegrity:
    """Tests for individual question integrity."""

    REQUIRED_FIELDS = [
        "id",
        "domain",
        "question",
        "difficulty",
        "expected_sources",
        "sub_questions",
        "evaluation_criteria",
        "tags"
    ]

    VALID_DOMAINS = [
        "AI-ML",
        "Investment",
        "Scientific",
        "Technical",
        "Interdisciplinary"
    ]

    VALID_DIFFICULTIES = ["easy", "medium", "hard"]

    def test_question_count(self, questions):
        """Verify there are exactly 500 questions."""
        assert len(questions) == 500, f"Expected 500 questions, found {len(questions)}"

    def test_all_questions_have_required_fields(self, questions):
        """Verify all questions have required fields."""
        for q in questions:
            for field in self.REQUIRED_FIELDS:
                assert field in q, f"Question {q.get('id', 'UNKNOWN')} missing field: {field}"

    def test_question_ids_unique(self, questions):
        """Verify all question IDs are unique."""
        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids)), "Duplicate question IDs found"

    def test_question_ids_format(self, questions):
        """Verify question IDs follow expected format."""
        id_patterns = {
            "AI-ML": r"^AIML-\d{3}$",
            "Investment": r"^INV-\d{3}$",
            "Scientific": r"^SCI-\d{3}$",
            "Technical": r"^TECH-\d{3}$",
            "Interdisciplinary": r"^INTER-\d{3}$"
        }
        import re
        for q in questions:
            domain = q["domain"]
            pattern = id_patterns.get(domain)
            if pattern:
                assert re.match(pattern, q["id"]), \
                    f"Question ID {q['id']} doesn't match pattern for domain {domain}"

    def test_domains_valid(self, questions):
        """Verify all domains are valid."""
        for q in questions:
            assert q["domain"] in self.VALID_DOMAINS, \
                f"Invalid domain '{q['domain']}' in question {q['id']}"

    def test_difficulties_valid(self, questions):
        """Verify all difficulties are valid."""
        for q in questions:
            assert q["difficulty"] in self.VALID_DIFFICULTIES, \
                f"Invalid difficulty '{q['difficulty']}' in question {q['id']}"

    def test_sub_questions_not_empty(self, questions):
        """Verify all questions have at least one sub-question."""
        for q in questions:
            assert len(q["sub_questions"]) >= 2, \
                f"Question {q['id']} has fewer than 2 sub-questions"
            assert len(q["sub_questions"]) <= 5, \
                f"Question {q['id']} has more than 5 sub-questions"

    def test_expected_sources_positive(self, questions):
        """Verify expected_sources is positive integer."""
        for q in questions:
            assert isinstance(q["expected_sources"], int), \
                f"Question {q['id']} expected_sources is not an integer"
            assert q["expected_sources"] > 0, \
                f"Question {q['id']} expected_sources must be positive"

    def test_tags_not_empty(self, questions):
        """Verify all questions have at least one tag."""
        for q in questions:
            assert len(q["tags"]) > 0, \
                f"Question {q['id']} has no tags"

    def test_question_text_not_empty(self, questions):
        """Verify all questions have non-empty text."""
        for q in questions:
            assert len(q["question"].strip()) > 20, \
                f"Question {q['id']} has too short question text"


# ============================================================================
# Domain Distribution Tests
# ============================================================================

class TestDomainDistribution:
    """Tests for domain distribution in the dataset."""

    def test_each_domain_has_100_questions(self, questions):
        """Verify each domain has exactly 100 questions."""
        domain_counts = {}
        for q in questions:
            domain = q["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        for domain, count in domain_counts.items():
            assert count == 100, f"Domain {domain} has {count} questions, expected 100"

    def test_difficulty_distribution(self, questions):
        """Verify reasonable difficulty distribution."""
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        for q in questions:
            difficulty_counts[q["difficulty"]] += 1

        # Each difficulty should have at least some questions
        for diff, count in difficulty_counts.items():
            assert count >= 20, f"Difficulty {diff} has only {count} questions"

        # Should have more medium and hard questions for a research benchmark
        assert difficulty_counts["medium"] + difficulty_counts["hard"] >= 300, \
            "Should have mostly medium and hard questions for research evaluation"


# ============================================================================
# Ground Truth Tests
# ============================================================================

class TestGroundTruth:
    """Tests for ground truth file integrity."""

    REQUIRED_GT_FIELDS = [
        "question_id",
        "question",
        "expert_sources",
        "key_findings",
        "known_counterarguments",
        "confidence_bounds",
        "evaluation_rubric"
    ]

    def test_ground_truth_count(self, ground_truth_files):
        """Verify there are exactly 20 ground truth files."""
        assert len(ground_truth_files) == 20, \
            f"Expected 20 ground truth files, found {len(ground_truth_files)}"

    def test_ground_truth_files_have_required_fields(self, ground_truth_files):
        """Verify all ground truth files have required fields."""
        for gt_file in ground_truth_files:
            with open(gt_file, 'r') as f:
                gt = json.load(f)

            for field in self.REQUIRED_GT_FIELDS:
                assert field in gt, f"Ground truth {gt_file.name} missing field: {field}"

    def test_ground_truth_ids_match_questions(self, ground_truth_files, questions):
        """Verify ground truth IDs match question IDs."""
        question_ids = {q["id"] for q in questions}

        for gt_file in ground_truth_files:
            with open(gt_file, 'r') as f:
                gt = json.load(f)

            assert gt["question_id"] in question_ids, \
                f"Ground truth {gt_file.name} references unknown question ID"

    def test_ground_truth_domain_distribution(self, ground_truth_files):
        """Verify ground truth has 4 per domain."""
        domain_counts = {"AIML": 0, "INV": 0, "SCI": 0, "TECH": 0, "INTER": 0}

        for gt_file in ground_truth_files:
            prefix = gt_file.stem.split("-")[0]
            if prefix in domain_counts:
                domain_counts[prefix] += 1

        for domain, count in domain_counts.items():
            assert count == 4, f"Domain prefix {domain} has {count} ground truth files, expected 4"

    def test_expert_sources_have_required_fields(self, ground_truth_files):
        """Verify expert sources have required fields."""
        for gt_file in ground_truth_files:
            with open(gt_file, 'r') as f:
                gt = json.load(f)

            for source in gt["expert_sources"]:
                assert "title" in source, f"Source in {gt_file.name} missing title"
                assert "relevance" in source, f"Source in {gt_file.name} missing relevance"

    def test_key_findings_have_required_fields(self, ground_truth_files):
        """Verify key findings have required fields."""
        for gt_file in ground_truth_files:
            with open(gt_file, 'r') as f:
                gt = json.load(f)

            for finding in gt["key_findings"]:
                assert "finding" in finding, f"Finding in {gt_file.name} missing 'finding'"
                assert "importance" in finding, f"Finding in {gt_file.name} missing 'importance'"

    def test_evaluation_rubric_has_sections(self, ground_truth_files):
        """Verify evaluation rubric has required sections."""
        for gt_file in ground_truth_files:
            with open(gt_file, 'r') as f:
                gt = json.load(f)

            rubric = gt["evaluation_rubric"]
            assert "must_include" in rubric, f"Rubric in {gt_file.name} missing must_include"
            assert "should_include" in rubric, f"Rubric in {gt_file.name} missing should_include"


# ============================================================================
# Evaluator Function Tests
# ============================================================================

class TestEvaluatorInit:
    """Tests for evaluator initialization."""

    def test_evaluator_loads_questions(self, evaluator):
        """Verify evaluator loads all questions."""
        assert len(evaluator.questions) == 500

    def test_evaluator_loads_ground_truth(self, evaluator):
        """Verify evaluator loads ground truth."""
        assert len(evaluator.ground_truth) == 20

    def test_get_question_by_id(self, evaluator):
        """Verify can retrieve question by ID."""
        q = evaluator.get_question("AIML-001")
        assert q is not None
        assert q["id"] == "AIML-001"

    def test_get_question_nonexistent(self, evaluator):
        """Verify returns None for nonexistent ID."""
        q = evaluator.get_question("NONEXISTENT-999")
        assert q is None


class TestDecompositionEvaluation:
    """Tests for decomposition evaluation."""

    def test_decomposition_returns_result(self, evaluator):
        """Verify decomposition evaluation returns EvaluationResult."""
        result = evaluator.evaluate_decomposition(
            "AIML-001",
            ["What is attention?", "What are state space models?"]
        )
        assert isinstance(result, EvaluationResult)

    def test_decomposition_score_range(self, evaluator):
        """Verify decomposition score is in valid range."""
        result = evaluator.evaluate_decomposition(
            "AIML-001",
            ["What is attention mechanism?", "How do state space models work?"]
        )
        assert 0 <= result.normalized_score <= 100

    def test_decomposition_empty_input(self, evaluator):
        """Verify handles empty sub-questions."""
        result = evaluator.evaluate_decomposition("AIML-001", [])
        assert result.normalized_score < 50

    def test_decomposition_nonexistent_question(self, evaluator):
        """Verify handles nonexistent question gracefully."""
        result = evaluator.evaluate_decomposition("NONEXISTENT", ["test"])
        assert result.score == 0

    def test_decomposition_good_coverage_scores_high(self, evaluator):
        """Verify good coverage gets high score."""
        q = evaluator.get_question("AIML-001")
        # Use actual sub-questions from the dataset
        result = evaluator.evaluate_decomposition("AIML-001", q["sub_questions"])
        assert result.normalized_score >= 60


class TestSourceCoverageEvaluation:
    """Tests for source coverage evaluation."""

    def test_source_coverage_returns_result(self, evaluator):
        """Verify source coverage evaluation returns EvaluationResult."""
        result = evaluator.evaluate_source_coverage(
            "AIML-001",
            [{"title": "Attention Is All You Need"}]
        )
        assert isinstance(result, EvaluationResult)

    def test_source_coverage_score_range(self, evaluator):
        """Verify source coverage score is in valid range."""
        result = evaluator.evaluate_source_coverage(
            "AIML-001",
            [{"title": "Test Source"}]
        )
        assert 0 <= result.normalized_score <= 100

    def test_source_coverage_empty_sources(self, evaluator):
        """Verify handles empty sources list."""
        result = evaluator.evaluate_source_coverage("AIML-001", [])
        assert result.normalized_score < 50

    def test_source_coverage_many_sources(self, evaluator):
        """Verify many sources gets higher score (for question without ground truth)."""
        # Use a question without ground truth to test quantity-based scoring
        sources = [{"title": f"Source {i}"} for i in range(10)]
        result = evaluator.evaluate_source_coverage("AIML-003", sources)
        assert result.normalized_score >= 50

    def test_source_coverage_matching_expert_sources(self, evaluator):
        """Verify matching expert sources gets high score."""
        # AIML-001 has ground truth with specific expert sources
        sources = [
            {"title": "Attention Is All You Need"},
            {"title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"},
            {"title": "Efficiently Modeling Long Sequences with Structured State Spaces"}
        ]
        result = evaluator.evaluate_source_coverage("AIML-001", sources)
        assert result.normalized_score >= 40  # Should match some expert sources


class TestSynthesisEvaluation:
    """Tests for synthesis evaluation."""

    def test_synthesis_returns_result(self, evaluator):
        """Verify synthesis evaluation returns EvaluationResult."""
        result = evaluator.evaluate_synthesis(
            "AIML-001",
            "This is a test synthesis about transformers and state space models."
        )
        assert isinstance(result, EvaluationResult)

    def test_synthesis_score_range(self, evaluator):
        """Verify synthesis score is in valid range."""
        result = evaluator.evaluate_synthesis(
            "AIML-001",
            "A comprehensive answer about the topic."
        )
        assert 0 <= result.normalized_score <= 100

    def test_synthesis_empty_text(self, evaluator):
        """Verify handles empty synthesis."""
        result = evaluator.evaluate_synthesis("AIML-001", "")
        assert result.normalized_score < 30

    def test_synthesis_long_text_scores_higher(self, evaluator):
        """Verify longer, substantive text scores higher."""
        short_result = evaluator.evaluate_synthesis("AIML-001", "Short answer.")
        long_result = evaluator.evaluate_synthesis(
            "AIML-001",
            """
            Transformers and state-space models represent two fundamentally different
            approaches to sequence modeling. Transformers use self-attention mechanisms
            with O(n^2) complexity, while state-space models like Mamba achieve O(n)
            complexity through their recurrent formulation. The attention mechanism
            allows transformers to directly relate any two positions in a sequence,
            making them excellent for tasks requiring retrieval and in-context learning.

            State-space models, particularly recent variants like S4 and Mamba, process
            sequences through learned state transitions. This enables linear-time
            processing but may lose some of the direct position-to-position reasoning
            that attention provides. However, selective state spaces in Mamba address
            some of these limitations.

            The practical trade-offs involve memory usage, inference speed, and task
            performance. Transformers remain dominant for most language tasks but
            SSMs show promise for very long sequences where quadratic attention
            becomes prohibitive.
            """
        )
        assert long_result.normalized_score > short_result.normalized_score


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_evaluate_decomposition_function(self):
        """Test convenience decomposition function."""
        score = evaluate_decomposition(
            "AIML-001",
            ["What is attention?", "What are SSMs?"]
        )
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_evaluate_source_coverage_function(self):
        """Test convenience source coverage function."""
        score = evaluate_source_coverage(
            "AIML-001",
            [{"title": "Test"}]
        )
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_evaluate_synthesis_function(self):
        """Test convenience synthesis function."""
        score = evaluate_synthesis(
            "AIML-001",
            "Test synthesis text."
        )
        assert isinstance(score, float)
        assert 0 <= score <= 100


class TestDatasetStatistics:
    """Tests for dataset statistics functionality."""

    def test_get_dataset_statistics(self, evaluator):
        """Verify dataset statistics are correct."""
        stats = evaluator.get_dataset_statistics()

        assert stats["total_questions"] == 500
        assert stats["questions_with_ground_truth"] == 20
        assert len(stats["domains"]) == 5

    def test_get_questions_by_domain(self, evaluator):
        """Verify filtering by domain works."""
        aiml_questions = evaluator.get_questions_by_domain("AI-ML")
        assert len(aiml_questions) == 100
        assert all(q["domain"] == "AI-ML" for q in aiml_questions)

    def test_get_questions_by_difficulty(self, evaluator):
        """Verify filtering by difficulty works."""
        hard_questions = evaluator.get_questions_by_difficulty("hard")
        assert len(hard_questions) > 0
        assert all(q["difficulty"] == "hard" for q in hard_questions)

    def test_get_questions_with_ground_truth(self, evaluator):
        """Verify filtering for ground truth works."""
        gt_questions = evaluator.get_questions_with_ground_truth()
        assert len(gt_questions) == 20


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
