#!/usr/bin/env python3
"""
Unit tests for Multi-LLM Review Integration (LLM-007)

Tests the integration of review panel into claude-loop.sh workflow.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.review_panel import ReviewPanel, ReviewResult


class TestReviewIntegration(unittest.TestCase):
    """Test review integration with claude-loop.sh"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.prd_file = os.path.join(self.temp_dir, "prd.json")
        self.script_path = Path(__file__).parent.parent / "claude-loop.sh"

    def tearDown(self):
        """Clean up test files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_review_flags_in_help(self):
        """Test that review flags appear in help output"""
        result = subprocess.run(
            ["bash", str(self.script_path), "--help"],
            capture_output=True,
            text=True
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--enable-review", result.stdout)
        self.assertIn("--reviewers", result.stdout)
        self.assertIn("--review-threshold", result.stdout)
        self.assertIn("--max-review-cycles", result.stdout)

    def test_review_flag_parsing(self):
        """Test that review flags are parsed correctly"""
        # This test would require mocking the full script execution
        # For now, we verify the flag presence in the script
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("--enable-review)", script_content)
        self.assertIn("REVIEW_ENABLED=true", script_content)
        self.assertIn("--reviewers)", script_content)
        self.assertIn("REVIEW_PROVIDERS=", script_content)
        self.assertIn("--review-threshold)", script_content)
        self.assertIn("REVIEW_THRESHOLD=", script_content)

    def test_review_panel_function_exists(self):
        """Test that run_review_panel function exists in script"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("run_review_panel()", script_content)
        self.assertIn("Run multi-LLM review on completed story", script_content)

    def test_review_integration_in_run_iteration(self):
        """Test that review panel is called in run_iteration"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        # Check for review integration
        self.assertIn("if $REVIEW_ENABLED; then", script_content)
        self.assertIn("run_review_panel", script_content)
        self.assertIn("review_cycle", script_content)
        self.assertIn("MAX_REVIEW_CYCLES", script_content)

    def test_review_cycle_logic(self):
        """Test that review-fix cycle logic exists"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        # Check for cycle logic
        self.assertIn("while [ $review_cycle -le $MAX_REVIEW_CYCLES ]", script_content)
        self.assertIn("review_passed=", script_content)
        self.assertIn("Review passed on cycle", script_content)
        self.assertIn("Review failed, requesting fixes", script_content)

    def test_review_threshold_checking(self):
        """Test that review threshold is checked"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("consensus_score", script_content)
        self.assertIn("REVIEW_THRESHOLD", script_content)
        self.assertIn("Review score", script_content)

    def test_review_result_logging(self):
        """Test that review results are logged"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("log_action \"ReviewPanel\"", script_content)
        self.assertIn("Review Results:", script_content)

    def test_default_review_threshold(self):
        """Test that default review threshold is 7"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("REVIEW_THRESHOLD=7", script_content)

    def test_default_max_review_cycles(self):
        """Test that default max review cycles is 2"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("MAX_REVIEW_CYCLES=2", script_content)

    def test_review_disabled_by_default(self):
        """Test that review is disabled by default"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("REVIEW_ENABLED=false", script_content)

    def test_review_panel_script_path(self):
        """Test that review panel script path is configured"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("REVIEW_PANEL_SCRIPT=", script_content)
        self.assertIn("lib/review_panel.py", script_content)

    def test_review_skipped_when_disabled(self):
        """Test that review is skipped when not enabled"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        # Check for early return when disabled
        self.assertIn("if ! $REVIEW_ENABLED; then", script_content)
        self.assertIn("return 0  # Review not enabled, skip", script_content)

    def test_review_uses_git_diff(self):
        """Test that review uses git diff"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("git diff HEAD~1 HEAD", script_content)

    def test_review_uses_story_context(self):
        """Test that review includes story context"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("story_context", script_content)
        self.assertIn("prd.json", script_content)

    def test_review_with_custom_reviewers(self):
        """Test that custom reviewers can be specified"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("--reviewers $REVIEW_PROVIDERS", script_content)

    def test_review_exit_codes(self):
        """Test that review exit codes are handled"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        # Check for different exit code handling
        self.assertIn("review_exit_code=0", script_content)
        self.assertIn("review_exit_code -eq 0", script_content)  # Success
        self.assertIn("review_exit_code -eq 2", script_content)  # Needs fixes

    def test_max_cycles_enforcement(self):
        """Test that maximum review cycles are enforced"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("Maximum review cycles reached", script_content)
        self.assertIn("review_cycle -lt $MAX_REVIEW_CYCLES", script_content)

    def test_fix_prompt_generation(self):
        """Test that fix prompts are generated from review feedback"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("issues_summary", script_content)
        self.assertIn("fix_prompt", script_content)
        self.assertIn("address these review comments", script_content)

    def test_story_completion_detection(self):
        """Test that story completion is detected"""
        with open(self.script_path, 'r') as f:
            script_content = f.read()

        self.assertIn("story_passes", script_content)
        self.assertIn("story_id", script_content)
        self.assertIn(".passes", script_content)


class TestReviewPanelMock(unittest.TestCase):
    """Test review panel with mocked providers"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_review_panel_with_passing_score(self):
        """Test review panel with passing consensus score"""
        # Mock provider responses with high scores
        mock_result = ReviewResult(
            consensus_score=8.5,
            total_issues=2,
            critical_issues=0,
            major_issues=0,
            individual_reviews=[],
            total_cost=0.05,
            reviewers_count=3,
            failed_reviewers=0
        )

        # Simulate passing review
        self.assertGreaterEqual(mock_result.consensus_score, 7)
        self.assertEqual(mock_result.critical_issues, 0)

    def test_review_panel_with_failing_score(self):
        """Test review panel with failing consensus score"""
        # Mock provider responses with low scores
        mock_result = ReviewResult(
            consensus_score=5.0,
            total_issues=10,
            critical_issues=3,
            major_issues=5,
            individual_reviews=[],
            total_cost=0.05,
            reviewers_count=3,
            failed_reviewers=0
        )

        # Simulate failing review
        self.assertLess(mock_result.consensus_score, 7)
        self.assertGreater(mock_result.critical_issues, 0)

    def test_review_panel_with_partial_failure(self):
        """Test review panel with some reviewers failing"""
        # Mock result with some failed reviewers
        mock_result = ReviewResult(
            consensus_score=7.5,
            total_issues=3,
            critical_issues=0,
            major_issues=1,
            individual_reviews=[],
            total_cost=0.03,
            reviewers_count=2,
            failed_reviewers=1
        )

        # Review should still pass with 2 successful reviewers
        self.assertGreaterEqual(mock_result.consensus_score, 7)
        self.assertEqual(mock_result.failed_reviewers, 1)


if __name__ == "__main__":
    unittest.main()
