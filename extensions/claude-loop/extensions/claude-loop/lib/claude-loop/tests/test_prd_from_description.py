#!/usr/bin/env python3
"""
Tests for prd-from-description.py (INV-008: Single-Command Entry Point)

Tests the auto-generation of PRDs from feature descriptions.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

# Import using importlib for hyphenated filename
import importlib.util

spec = importlib.util.spec_from_file_location(
    "prd_from_description", lib_dir / "prd-from-description.py"
)
assert spec is not None and spec.loader is not None
prd_gen = importlib.util.module_from_spec(spec)
sys.modules["prd_from_description"] = prd_gen
spec.loader.exec_module(prd_gen)


class TestProjectIdGeneration(unittest.TestCase):
    """Test project ID generation from descriptions."""

    def test_simple_description(self):
        """Test ID generation from simple description."""
        project_id = prd_gen.generate_project_id("Add dark mode toggle")
        self.assertIn("dark", project_id)
        self.assertIn("mode", project_id)

    def test_stopwords_filtered(self):
        """Test that common words are filtered out."""
        project_id = prd_gen.generate_project_id("Add a new feature to the app")
        # Should not contain 'a', 'the', 'to', 'add'
        parts = project_id.split('-')
        self.assertNotIn('a', parts)
        self.assertNotIn('the', parts)

    def test_uniqueness_via_hash(self):
        """Test that different descriptions produce different IDs."""
        id1 = prd_gen.generate_project_id("Add user auth")
        id2 = prd_gen.generate_project_id("Add user authentication")
        # Should have different hash suffixes
        self.assertNotEqual(id1, id2)

    def test_short_description(self):
        """Test handling of very short descriptions."""
        project_id = prd_gen.generate_project_id("Fix bug")
        self.assertIsNotNone(project_id)
        self.assertGreater(len(project_id), 4)  # At least hash suffix


class TestFeatureTypeDetection(unittest.TestCase):
    """Test detection of feature types from descriptions."""

    def test_auth_keywords(self):
        """Test detection of authentication-related features."""
        types = prd_gen.detect_feature_type("Add user authentication with OAuth")
        self.assertIn("auth", types)
        self.assertIn("oauth", types)

    def test_api_keywords(self):
        """Test detection of API-related features."""
        types = prd_gen.detect_feature_type("Create REST API endpoints")
        self.assertIn("api", types)
        self.assertIn("endpoint", types)

    def test_ui_keywords(self):
        """Test detection of UI-related features."""
        types = prd_gen.detect_feature_type("Build dashboard component")
        self.assertIn("ui", types)
        self.assertIn("dashboard", types)
        self.assertIn("component", types)

    def test_always_includes_setup(self):
        """Test that setup is always included."""
        types = prd_gen.detect_feature_type("Random feature description")
        self.assertIn("setup", types)

    def test_always_includes_test_and_docs(self):
        """Test that test and docs are included."""
        types = prd_gen.detect_feature_type("Add some feature")
        self.assertIn("test", types)
        self.assertIn("docs", types)


class TestStoryCountEstimation(unittest.TestCase):
    """Test story count estimation based on complexity."""

    def test_low_complexity(self):
        """Test story count for low complexity features."""
        count = prd_gen.estimate_story_count("Fix a typo", 0)
        self.assertGreaterEqual(count, 1)
        self.assertLessEqual(count, 4)

    def test_medium_complexity(self):
        """Test story count for medium complexity features."""
        count = prd_gen.estimate_story_count("Add user management", 2)
        self.assertGreaterEqual(count, 4)
        self.assertLessEqual(count, 8)

    def test_high_complexity(self):
        """Test story count for high complexity features."""
        count = prd_gen.estimate_story_count("Enterprise dashboard", 4)
        self.assertGreaterEqual(count, 8)
        self.assertLessEqual(count, 15)

    def test_keyword_adjustment(self):
        """Test that keywords adjust story count."""
        base_count = prd_gen.estimate_story_count("Simple feature", 2)
        oauth_count = prd_gen.estimate_story_count("Add OAuth authentication", 2)
        # OAuth should add more stories
        self.assertGreater(oauth_count, base_count)


class TestStoryGeneration(unittest.TestCase):
    """Test user story generation."""

    def test_generates_stories(self):
        """Test that stories are generated."""
        stories = prd_gen.generate_stories_for_description(
            "Add user authentication",
            "AUTH",
            2
        )
        self.assertGreater(len(stories), 0)

    def test_story_structure(self):
        """Test that stories have correct structure."""
        stories = prd_gen.generate_stories_for_description(
            "Add API endpoints",
            "API",
            2
        )
        for story in stories:
            self.assertIsNotNone(story.id)
            self.assertIsNotNone(story.title)
            self.assertIsNotNone(story.description)
            self.assertIsInstance(story.acceptanceCriteria, list)
            self.assertGreater(len(story.acceptanceCriteria), 0)
            self.assertIsInstance(story.priority, int)
            self.assertFalse(story.passes)

    def test_story_dependencies(self):
        """Test that stories have proper dependencies (except first)."""
        stories = prd_gen.generate_stories_for_description(
            "Build full feature",
            "FEAT",
            3
        )
        # First story should have no dependencies
        self.assertEqual(len(stories[0].dependencies), 0)

        # Subsequent stories should depend on previous
        for i in range(1, len(stories)):
            expected_dep = stories[i - 1].id
            self.assertIn(expected_dep, stories[i].dependencies)

    def test_story_ids_sequential(self):
        """Test that story IDs are sequential."""
        stories = prd_gen.generate_stories_for_description(
            "Add feature",
            "FEAT",
            2
        )
        for i, story in enumerate(stories, start=1):
            expected_suffix = f"-{str(i).zfill(3)}"
            self.assertTrue(story.id.endswith(expected_suffix))


class TestPRDGeneration(unittest.TestCase):
    """Test complete PRD generation."""

    def test_generates_prd(self):
        """Test that a complete PRD is generated."""
        prd = prd_gen.generate_prd_from_description(
            "Add dark mode toggle"
        )
        self.assertIsNotNone(prd)
        self.assertIsNotNone(prd.project)
        self.assertIsNotNone(prd.branchName)
        self.assertIsNotNone(prd.description)
        self.assertGreater(len(prd.userStories), 0)

    def test_branch_name_format(self):
        """Test that branch name follows expected format."""
        prd = prd_gen.generate_prd_from_description(
            "Add user profiles"
        )
        self.assertTrue(prd.branchName.startswith("feature/"))

    def test_complexity_detection(self):
        """Test that complexity is detected."""
        prd = prd_gen.generate_prd_from_description(
            "Add simple feature"
        )
        self.assertIn(prd.complexity_level, range(5))
        self.assertIn(prd.track, ["quick", "standard", "enterprise"])
        self.assertGreater(len(prd.phases), 0)

    def test_saves_to_file(self):
        """Test that PRD can be saved to a file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            prd = prd_gen.generate_prd_from_description(
                "Add notification system",
                output_path
            )

            self.assertTrue(os.path.exists(output_path))

            with open(output_path) as f:
                saved_prd = json.load(f)

            self.assertEqual(saved_prd['project'], prd.project)
            self.assertEqual(saved_prd['branchName'], prd.branchName)
            self.assertEqual(len(saved_prd['userStories']), len(prd.userStories))
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestAnalysis(unittest.TestCase):
    """Test description analysis."""

    def test_analyze_returns_dict(self):
        """Test that analyze returns a dictionary."""
        result = prd_gen.analyze_description("Add user auth")
        self.assertIsInstance(result, dict)

    def test_analyze_includes_required_fields(self):
        """Test that analyze includes all required fields."""
        result = prd_gen.analyze_description("Build dashboard")
        self.assertIn("description", result)
        self.assertIn("project_id", result)
        self.assertIn("branch_name", result)
        self.assertIn("complexity", result)
        self.assertIn("track", result)
        self.assertIn("phases", result)
        self.assertIn("detected_features", result)
        self.assertIn("estimated_stories", result)

    def test_analyze_complexity_structure(self):
        """Test that complexity has correct structure."""
        result = prd_gen.analyze_description("Add feature")
        complexity = result["complexity"]
        self.assertIn("level", complexity)
        self.assertIn("name", complexity)
        self.assertIn("description", complexity)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""

    def test_full_workflow(self):
        """Test the complete workflow from description to PRD."""
        description = "Add user authentication with OAuth, including login, register, and password reset"

        # Generate PRD
        prd = prd_gen.generate_prd_from_description(description)

        # Verify all required fields are present
        self.assertEqual(prd.description, description)
        self.assertTrue(prd.auto_detected)

        # Verify stories make sense
        auth_stories = [s for s in prd.userStories if "auth" in s.title.lower()]
        self.assertGreater(len(auth_stories), 0)

    def test_backward_compatibility_with_prd_flag(self):
        """Test that generated PRD works with existing PRD format."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            prd_gen.generate_prd_from_description(
                "Add simple feature",
                output_path
            )

            with open(output_path) as f:
                saved_prd = json.load(f)

            # Verify standard PRD fields
            self.assertIn("project", saved_prd)
            self.assertIn("branchName", saved_prd)
            self.assertIn("description", saved_prd)
            self.assertIn("userStories", saved_prd)

            # Verify each story has required fields
            for story in saved_prd["userStories"]:
                self.assertIn("id", story)
                self.assertIn("title", story)
                self.assertIn("description", story)
                self.assertIn("acceptanceCriteria", story)
                self.assertIn("priority", story)
                self.assertIn("passes", story)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == "__main__":
    unittest.main()
