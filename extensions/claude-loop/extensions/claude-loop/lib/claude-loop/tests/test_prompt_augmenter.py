#!/usr/bin/env python3
"""
Unit tests for prompt-augmenter.py

Tests the experience-augmented prompts system including:
- AugmentedExperience dataclass
- AugmentationResult dataclass
- PromptAugmenter class
- Domain detection integration
- Experience retrieval and filtering
- Prompt formatting
"""

import runpy
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# Import module using runpy (handles hyphenated filename)
MODULE_PATH = Path(__file__).parent.parent / "lib" / "prompt-augmenter.py"
augmenter_module = runpy.run_path(str(MODULE_PATH))

# Extract classes and functions
PromptAugmenter = augmenter_module["PromptAugmenter"]
AugmentedExperience = augmenter_module["AugmentedExperience"]
AugmentationResult = augmenter_module["AugmentationResult"]

# Constants
MIN_HELPFUL_RATE = augmenter_module["MIN_HELPFUL_RATE"]
MAX_EXPERIENCES = augmenter_module["MAX_EXPERIENCES"]


class TestAugmentedExperience(unittest.TestCase):
    """Test AugmentedExperience dataclass."""

    def test_create_experience(self):
        """Test creating an augmented experience."""
        exp = AugmentedExperience(
            experience_id="EXP-12345",
            problem_summary="Build failed with missing dependency",
            solution_approach="Add missing import to requirements.txt",
            success_rate=0.85,
            helpful_rate=0.75,
            similarity_score=0.82,
            domain="web_backend",
        )

        self.assertEqual(exp.experience_id, "EXP-12345")
        self.assertEqual(exp.domain, "web_backend")
        self.assertAlmostEqual(exp.helpful_rate, 0.75)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        exp = AugmentedExperience(
            experience_id="EXP-001",
            problem_summary="Test failure",
            solution_approach="Fix assertion",
            success_rate=0.9,
            helpful_rate=0.8,
            similarity_score=0.85,
            domain="cli_tool",
        )

        d = exp.to_dict()

        self.assertEqual(d["experience_id"], "EXP-001")
        self.assertEqual(d["domain"], "cli_tool")
        self.assertEqual(d["success_rate"], 0.9)


class TestAugmentationResult(unittest.TestCase):
    """Test AugmentationResult dataclass."""

    def test_create_result(self):
        """Test creating an augmentation result."""
        result = AugmentationResult(
            experiences=[],
            domain_detected="unity_game",
            domain_confidence="high",
            augmented=False,
            formatted_section="",
            retrieval_count=0,
            filtered_count=0,
        )

        self.assertEqual(result.domain_detected, "unity_game")
        self.assertFalse(result.augmented)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        exp = AugmentedExperience(
            experience_id="EXP-001",
            problem_summary="Error",
            solution_approach="Fix",
            success_rate=0.9,
            helpful_rate=0.8,
            similarity_score=0.85,
            domain="web_frontend",
        )

        result = AugmentationResult(
            experiences=[exp],
            domain_detected="web_frontend",
            domain_confidence="medium",
            augmented=True,
            formatted_section="## Section",
            retrieval_count=3,
            filtered_count=1,
        )

        d = result.to_dict()

        self.assertEqual(d["domain_detected"], "web_frontend")
        self.assertTrue(d["augmented"])
        self.assertEqual(d["retrieval_count"], 3)
        self.assertEqual(len(d["experiences"]), 1)


class TestPromptAugmenter(unittest.TestCase):
    """Test PromptAugmenter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.test_dir) / ".claude-loop" / "experiences"
        self.db_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_init_default(self):
        """Test default initialization."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        self.assertIsNotNone(augmenter)
        self.assertEqual(augmenter.min_helpful_rate, MIN_HELPFUL_RATE)
        self.assertEqual(augmenter.max_experiences, MAX_EXPERIENCES)

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
            min_helpful_rate=0.5,
            max_experiences=5,
        )

        self.assertEqual(augmenter.min_helpful_rate, 0.5)
        self.assertEqual(augmenter.max_experiences, 5)

    def test_augment_prompt_no_experiences(self):
        """Test augmentation with no experiences available."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        result = augmenter.augment_prompt("Test problem description")

        self.assertEqual(result.retrieval_count, 0)
        self.assertEqual(len(result.experiences), 0)
        self.assertFalse(result.augmented)
        self.assertEqual(result.formatted_section, "")

    def test_augment_prompt_explicit_domain(self):
        """Test augmentation with explicit domain."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        result = augmenter.augment_prompt(
            "Build failed",
            domain_type="unity_xr",
        )

        self.assertEqual(result.domain_detected, "unity_xr")
        self.assertEqual(result.domain_confidence, "explicit")

    def test_summarize_text_short(self):
        """Test text summarization with short text."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        short_text = "Short problem"
        result = augmenter._summarize_text(short_text, 100)

        self.assertEqual(result, "Short problem")

    def test_summarize_text_long(self):
        """Test text summarization with long text."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        long_text = "A" * 150
        result = augmenter._summarize_text(long_text, 100)

        self.assertEqual(len(result), 100)
        self.assertTrue(result.endswith("..."))

    def test_format_experiences_section_empty(self):
        """Test formatting with no experiences."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        result = augmenter._format_experiences_section([], "web_backend")

        self.assertEqual(result, "")

    def test_format_experiences_section_with_experiences(self):
        """Test formatting with experiences."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        experiences = [
            AugmentedExperience(
                experience_id="EXP-001",
                problem_summary="Import error",
                solution_approach="Add missing dependency",
                success_rate=0.9,
                helpful_rate=0.8,
                similarity_score=0.85,
                domain="web_backend",
            ),
            AugmentedExperience(
                experience_id="EXP-002",
                problem_summary="Type error",
                solution_approach="Fix type annotations",
                success_rate=0.85,
                helpful_rate=0.75,
                similarity_score=0.78,
                domain="web_backend",
            ),
        ]

        result = augmenter._format_experiences_section(experiences, "web_backend")

        # Check section header
        self.assertIn("## Relevant Past Experiences", result)
        self.assertIn("web_backend", result)

        # Check experience 1
        self.assertIn("### Experience 1", result)
        self.assertIn("Import error", result)
        self.assertIn("Add missing dependency", result)

        # Check experience 2
        self.assertIn("### Experience 2", result)
        self.assertIn("Type error", result)

        # Check metrics (note: bold markdown syntax used)
        self.assertIn("**Success Rate**:", result)
        self.assertIn("**Helpful Rate**:", result)
        self.assertIn("**Similarity**:", result)

    def test_check_augmentation_available(self):
        """Test checking augmentation availability."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        result = augmenter.check_augmentation_available("Test problem")

        self.assertIn("available", result)
        self.assertIn("domain", result)
        self.assertIn("experience_count", result)
        self.assertIn("experiences_preview", result)

    def test_log_augmentation(self):
        """Test augmentation logging."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        # Create execution log directory
        log_dir = Path(self.test_dir) / ".claude-loop"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Patch the log file path
        log_file = log_dir / "execution_log.jsonl"

        with patch.object(augmenter_module["Path"], "__new__", return_value=log_file):
            result = AugmentationResult(
                experiences=[],
                domain_detected="cli_tool",
                domain_confidence="high",
                augmented=False,
                formatted_section="",
                retrieval_count=0,
                filtered_count=0,
            )

            # This should not raise
            augmenter.log_augmentation(result, "US-001", success=True)


class TestPromptAugmenterWithMockedRetriever(unittest.TestCase):
    """Test PromptAugmenter with mocked retriever."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.test_dir) / ".claude-loop" / "experiences"
        self.db_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_filter_by_helpful_rate(self):
        """Test that experiences are filtered by helpful_rate."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
            min_helpful_rate=0.5,  # Set threshold
        )

        # Mock retriever if available
        if augmenter.retriever is not None:
            # Create mock results
            mock_result_high = MagicMock()
            mock_result_high.helpful_rate = 0.8
            mock_result_high.similarity_score = 0.9
            mock_result_high.recency_factor = 0.9
            mock_result_high.ranking_score = 0.8

            mock_exp_high = MagicMock()
            mock_exp_high.id = "EXP-HIGH"
            mock_exp_high.problem_signature = "High rate problem"
            mock_exp_high.solution_approach = "High rate solution"
            mock_exp_high.success_count = 8
            mock_exp_high.retrieval_count = 10
            mock_exp_high.domain_context = MagicMock()
            mock_exp_high.domain_context.project_type = "web_backend"
            mock_result_high.experience = mock_exp_high

            mock_result_low = MagicMock()
            mock_result_low.helpful_rate = 0.2  # Below threshold
            mock_result_low.similarity_score = 0.85
            mock_result_low.experience = MagicMock()

            augmenter.retriever.retrieve_similar = MagicMock(
                return_value=[mock_result_high, mock_result_low]
            )

            result = augmenter.augment_prompt("Test problem")

            # Only high rate should be included
            self.assertEqual(len(result.experiences), 1)
            self.assertEqual(result.experiences[0].experience_id, "EXP-HIGH")
            self.assertEqual(result.filtered_count, 1)


class TestConstants(unittest.TestCase):
    """Test module constants."""

    def test_min_helpful_rate(self):
        """Test minimum helpful rate value."""
        self.assertEqual(MIN_HELPFUL_RATE, 0.30)

    def test_max_experiences(self):
        """Test maximum experiences value."""
        self.assertEqual(MAX_EXPERIENCES, 3)


class TestCLICommands(unittest.TestCase):
    """Test CLI command functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_create_parser(self):
        """Test argument parser creation."""
        create_parser = augmenter_module["create_parser"]
        parser = create_parser()

        self.assertIsNotNone(parser)
        # Test that parser has description
        self.assertIn("Experience-Augmented", parser.description)


class TestFormattingEdgeCases(unittest.TestCase):
    """Test edge cases in formatting."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.test_dir) / ".claude-loop" / "experiences"
        self.db_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_format_with_special_characters(self):
        """Test formatting with special characters in text."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        experiences = [
            AugmentedExperience(
                experience_id="EXP-001",
                problem_summary="Error: `undefined` is not a function",
                solution_approach="Check for null values with `if (x !== null)`",
                success_rate=0.9,
                helpful_rate=0.8,
                similarity_score=0.85,
                domain="web_frontend",
            ),
        ]

        result = augmenter._format_experiences_section(experiences, "web_frontend")

        self.assertIn("`undefined`", result)
        self.assertIn("`if (x !== null)`", result)

    def test_format_with_multiline_solution(self):
        """Test formatting with multiline solution approach."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        # Multiline will be truncated
        multiline_solution = "Step 1: Do this\nStep 2: Do that\nStep 3: Final step"
        truncated = augmenter._summarize_text(multiline_solution, 30)

        self.assertEqual(len(truncated), 30)
        self.assertTrue(truncated.endswith("..."))

    def test_format_percentage_display(self):
        """Test that percentages are displayed correctly."""
        augmenter = PromptAugmenter(
            db_dir=str(self.db_dir),
            project_path=self.test_dir,
        )

        experiences = [
            AugmentedExperience(
                experience_id="EXP-001",
                problem_summary="Test",
                solution_approach="Fix",
                success_rate=0.95,
                helpful_rate=0.82,
                similarity_score=0.78,
                domain="web_backend",
            ),
        ]

        result = augmenter._format_experiences_section(experiences, "web_backend")

        # Check percentages are formatted
        self.assertIn("95%", result)
        self.assertIn("82%", result)
        self.assertIn("78%", result)


if __name__ == "__main__":
    unittest.main()
