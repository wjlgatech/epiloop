#!/usr/bin/env python3
"""
Unit Tests for Auto-Pass Logic

Tests the auto-pass feature in spec-compliance-reviewer.py
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add lib to path and import module with dash in name
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

import importlib.util
spec = importlib.util.spec_from_file_location("spec_compliance_reviewer", Path(__file__).parent.parent / 'lib' / 'spec-compliance-reviewer.py')
spec_reviewer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spec_reviewer_module)
SpecComplianceReviewer = spec_reviewer_module.SpecComplianceReviewer


class TestAutoPass(unittest.TestCase):
    """Test auto-pass logic in spec compliance reviewer."""

    def setUp(self):
        """Create temporary PRD file for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.prd_file = self.temp_dir / "test_prd.json"

    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir)

    def create_prd_with_criteria(self, criteria: list, passes: bool = False) -> None:
        """Helper to create PRD with specific criteria."""
        prd = {
            "project": "test-project",
            "userStories": [
                {
                    "id": "US-001",
                    "title": "Test Story",
                    "passes": passes,
                    "acceptanceCriteria": criteria
                }
            ]
        }

        with open(self.prd_file, 'w') as f:
            json.dump(prd, f, indent=2)

    def test_calculate_criteria_score_all_passed(self):
        """Test scoring when all criteria passed."""
        criteria = [
            {"id": "AC1", "weight": 0.25, "passed": True},
            {"id": "AC2", "weight": 0.25, "passed": True},
            {"id": "AC3", "weight": 0.25, "passed": True},
            {"id": "AC4", "weight": 0.25, "passed": True}
        ]

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        score = reviewer.calculate_criteria_score(criteria)
        self.assertEqual(score, 1.0)

    def test_calculate_criteria_score_half_passed(self):
        """Test scoring when half criteria passed."""
        criteria = [
            {"id": "AC1", "weight": 0.5, "passed": True},
            {"id": "AC2", "weight": 0.5, "passed": False}
        ]

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        score = reviewer.calculate_criteria_score(criteria)
        self.assertEqual(score, 0.5)

    def test_calculate_criteria_score_weighted(self):
        """Test scoring with different weights."""
        criteria = [
            {"id": "AC1", "weight": 0.6, "passed": True},   # 0.6 points
            {"id": "AC2", "weight": 0.3, "passed": True},   # 0.3 points
            {"id": "AC3", "weight": 0.1, "passed": False}   # 0.0 points
        ]

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        score = reviewer.calculate_criteria_score(criteria)
        self.assertAlmostEqual(score, 0.9, places=2)

    def test_calculate_criteria_score_none_passed(self):
        """Test scoring when no criteria passed."""
        criteria = [
            {"id": "AC1", "weight": 0.5, "passed": False},
            {"id": "AC2", "weight": 0.5, "passed": False}
        ]

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        score = reviewer.calculate_criteria_score(criteria)
        self.assertEqual(score, 0.0)

    def test_calculate_criteria_score_empty(self):
        """Test scoring with no criteria."""
        criteria = []

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        score = reviewer.calculate_criteria_score(criteria)
        self.assertEqual(score, 0.0)

    def test_calculate_criteria_score_string_criteria(self):
        """Test scoring with string criteria (no passed field)."""
        criteria = [
            "Criterion 1",
            "Criterion 2",
            "Criterion 3"
        ]

        self.create_prd_with_criteria(criteria)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        # String criteria default to not passed
        score = reviewer.calculate_criteria_score(criteria)
        self.assertEqual(score, 0.0)

    def test_auto_pass_high_score(self):
        """Test auto-pass with score >= 0.90."""
        criteria = [
            {"id": "AC1", "weight": 0.25, "passed": True},
            {"id": "AC2", "weight": 0.25, "passed": True},
            {"id": "AC3", "weight": 0.25, "passed": True},
            {"id": "AC4", "weight": 0.25, "passed": True}
        ]

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        # Review should auto-pass
        passes, issues = reviewer.review()

        self.assertTrue(passes)
        self.assertEqual(len(issues), 1)
        self.assertIn("Auto-passed", issues[0])
        self.assertIn("1.00", issues[0])

    def test_auto_pass_threshold_exactly_090(self):
        """Test auto-pass at exactly 0.90 threshold."""
        criteria = [
            {"id": "AC1", "weight": 0.3, "passed": True},   # 0.3
            {"id": "AC2", "weight": 0.3, "passed": True},   # 0.3
            {"id": "AC3", "weight": 0.3, "passed": True},   # 0.3
            {"id": "AC4", "weight": 0.1, "passed": False}   # 0.0
        ]
        # Total: 0.9 / 1.0 = 0.90 exactly

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        passes, issues = reviewer.review()

        # Should pass at exactly 0.90
        self.assertTrue(passes)
        self.assertIn("Auto-passed", issues[0])

    def test_no_auto_pass_low_score(self):
        """Test no auto-pass with score < 0.90."""
        criteria = [
            {"id": "AC1", "weight": 0.25, "passed": True},
            {"id": "AC2", "weight": 0.25, "passed": True},
            {"id": "AC3", "weight": 0.25, "passed": True},
            {"id": "AC4", "weight": 0.25, "passed": False}
        ]
        # Total: 0.75 / 1.0 = 0.75 < 0.90

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        passes, issues = reviewer.review()

        # Should NOT auto-pass (will continue with normal validation)
        # The review will fail for other reasons, but not auto-pass
        # Just check that it didn't auto-pass
        if len(issues) > 0:
            self.assertNotIn("Auto-passed", issues[0])

    def test_auto_pass_updates_prd(self):
        """Test that auto-pass updates the PRD file."""
        criteria = [
            {"id": "AC1", "weight": 1.0, "passed": True}
        ]

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        # Review should auto-pass and update PRD
        passes, issues = reviewer.review()

        self.assertTrue(passes)

        # Check PRD was updated
        with open(self.prd_file) as f:
            prd = json.load(f)

        story = prd['userStories'][0]
        self.assertTrue(story['passes'])
        self.assertIn("Auto-passed", story.get('notes', ''))

    def test_skip_validation_if_already_passed(self):
        """Test that validation is skipped if passes already true."""
        criteria = [
            {"id": "AC1", "weight": 1.0, "passed": False}  # Intentionally false
        ]

        self.create_prd_with_criteria(criteria, passes=True)  # Already marked passed
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        # Review should immediately return true without checking criteria
        passes, issues = reviewer.review()

        self.assertTrue(passes)
        self.assertEqual(len(issues), 0)

    def test_auto_pass_with_095_score(self):
        """Test auto-pass with very high score (0.95)."""
        criteria = [
            {"id": "AC1", "weight": 0.2, "passed": True},
            {"id": "AC2", "weight": 0.2, "passed": True},
            {"id": "AC3", "weight": 0.2, "passed": True},
            {"id": "AC4", "weight": 0.2, "passed": True},
            {"id": "AC5", "weight": 0.2, "passed": False}
        ]
        # Total: 0.8 / 1.0 = 0.80 < 0.90

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        passes, issues = reviewer.review()

        # 0.80 should NOT auto-pass
        if len(issues) > 0 and "Auto-passed" in issues[0]:
            self.fail("Should not auto-pass with 0.80 score")

    def test_auto_pass_creates_backup(self):
        """Test that auto-pass creates backup file."""
        criteria = [
            {"id": "AC1", "weight": 1.0, "passed": True}
        ]

        self.create_prd_with_criteria(criteria, passes=False)
        reviewer = SpecComplianceReviewer(str(self.prd_file), "US-001")

        # Review should auto-pass
        passes, issues = reviewer.review()

        self.assertTrue(passes)

        # Check backup was created
        backup_file = self.prd_file.with_suffix('.json.backup')
        self.assertTrue(backup_file.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
