#!/usr/bin/env python3
"""
Unit Tests for PRD Updater Tool

Tests the enhanced PRD updater with atomic writes, backups, and validation.
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Add lib to path and import module with dash in name
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

import importlib.util
spec = importlib.util.spec_from_file_location("prd_updater", Path(__file__).parent.parent / 'lib' / 'prd-updater.py')
prd_updater_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prd_updater_module)
PRDUpdater = prd_updater_module.PRDUpdater


class TestPRDUpdater(unittest.TestCase):
    """Test PRD Updater functionality."""

    def setUp(self):
        """Create temporary PRD file for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.prd_file = self.temp_dir / "test_prd.json"

        # Create sample PRD
        self.sample_prd = {
            "project": "test-project",
            "branchName": "test-branch",
            "userStories": [
                {
                    "id": "US-001",
                    "title": "Test Story 1",
                    "passes": False,
                    "priority": 1,
                    "notes": "",
                    "acceptanceCriteria": [
                        {"id": "AC1", "description": "Criterion 1", "weight": 0.5, "passed": True},
                        {"id": "AC2", "description": "Criterion 2", "weight": 0.5, "passed": True}
                    ]
                },
                {
                    "id": "US-002",
                    "title": "Test Story 2",
                    "passes": False,
                    "priority": 2,
                    "notes": ""
                },
                {
                    "id": "US-003",
                    "title": "Already Complete",
                    "passes": True,
                    "priority": 3,
                    "notes": "Previously completed"
                }
            ]
        }

        with open(self.prd_file, 'w') as f:
            json.dump(self.sample_prd, f, indent=2)

    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir)

    def test_init_with_valid_file(self):
        """Test initializing updater with valid PRD file."""
        updater = PRDUpdater(str(self.prd_file))
        self.assertEqual(updater.prd_file, self.prd_file)

    def test_init_with_nonexistent_file(self):
        """Test initializing updater with non-existent file raises error."""
        with self.assertRaises(FileNotFoundError):
            PRDUpdater(str(self.temp_dir / "nonexistent.json"))

    def test_load_prd(self):
        """Test loading PRD from file."""
        updater = PRDUpdater(str(self.prd_file))
        prd = updater.load_prd()

        self.assertEqual(prd['project'], 'test-project')
        self.assertEqual(len(prd['userStories']), 3)

    def test_find_story_existing(self):
        """Test finding existing story."""
        updater = PRDUpdater(str(self.prd_file))
        prd = updater.load_prd()
        story = updater.find_story(prd, "US-001")

        self.assertIsNotNone(story)
        self.assertEqual(story['id'], "US-001")
        self.assertEqual(story['title'], "Test Story 1")

    def test_find_story_nonexistent(self):
        """Test finding non-existent story returns None."""
        updater = PRDUpdater(str(self.prd_file))
        prd = updater.load_prd()
        story = updater.find_story(prd, "US-999")

        self.assertIsNone(story)

    def test_mark_complete_success(self):
        """Test marking story as complete."""
        updater = PRDUpdater(str(self.prd_file))
        success = updater.mark_complete("US-001", "Test completion notes")

        self.assertTrue(success)

        # Verify PRD was updated
        prd = updater.load_prd()
        story = updater.find_story(prd, "US-001")

        self.assertTrue(story['passes'])
        self.assertEqual(story['notes'], "Test completion notes")

    def test_mark_complete_with_commit_sha(self):
        """Test marking complete with commit SHA."""
        updater = PRDUpdater(str(self.prd_file))
        success = updater.mark_complete("US-001", "Test notes", commit_sha="abc123")

        self.assertTrue(success)

        # Verify commit SHA was stored
        prd = updater.load_prd()
        story = updater.find_story(prd, "US-001")

        self.assertEqual(story['implementationCommit'], "abc123")

    def test_mark_complete_already_complete(self):
        """Test marking already complete story."""
        updater = PRDUpdater(str(self.prd_file))
        success = updater.mark_complete("US-003", "New notes")

        # Should still succeed
        self.assertTrue(success)

        # But notes should not change
        prd = updater.load_prd()
        story = updater.find_story(prd, "US-003")
        self.assertEqual(story['notes'], "Previously completed")

    def test_mark_complete_nonexistent(self):
        """Test marking non-existent story fails."""
        updater = PRDUpdater(str(self.prd_file))
        success = updater.mark_complete("US-999", "Test notes")

        self.assertFalse(success)

    def test_mark_complete_auto_timestamp(self):
        """Test auto-timestamp when no notes provided."""
        updater = PRDUpdater(str(self.prd_file))
        before = datetime.now()
        success = updater.mark_complete("US-002")
        after = datetime.now()

        self.assertTrue(success)

        prd = updater.load_prd()
        story = updater.find_story(prd, "US-002")

        # Check notes contain timestamp
        self.assertIn("Completed on", story['notes'])

        # Parse timestamp and verify it's between before/after
        # (simplified check - just verify format)
        self.assertRegex(story['notes'], r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    def test_atomic_write_creates_backup(self):
        """Test that backup is created before overwriting."""
        updater = PRDUpdater(str(self.prd_file))
        updater.mark_complete("US-001", "Test")

        # Check backup exists
        backup_file = self.prd_file.with_suffix('.json.backup')
        self.assertTrue(backup_file.exists())

        # Verify backup has original content
        with open(backup_file) as f:
            backup_prd = json.load(f)

        # Backup should have passes=False for US-001
        backup_story = next(s for s in backup_prd['userStories'] if s['id'] == 'US-001')
        self.assertFalse(backup_story['passes'])

    def test_save_prd_validates_json(self):
        """Test that save validates generated JSON."""
        updater = PRDUpdater(str(self.prd_file))
        prd = updater.load_prd()

        # Try to save valid PRD (should work)
        updater.save_prd(prd)

        # Verify file still has valid JSON
        with open(self.prd_file) as f:
            reloaded = json.load(f)

        self.assertEqual(reloaded['project'], 'test-project')

    def test_get_status_existing(self):
        """Test getting status of existing story."""
        updater = PRDUpdater(str(self.prd_file))
        story = updater.get_status("US-001")

        self.assertIsNotNone(story)
        self.assertEqual(story['id'], "US-001")
        self.assertFalse(story['passes'])

    def test_get_status_nonexistent(self):
        """Test getting status of non-existent story."""
        updater = PRDUpdater(str(self.prd_file))
        story = updater.get_status("US-999")

        self.assertIsNone(story)

    def test_list_incomplete(self):
        """Test listing incomplete stories."""
        updater = PRDUpdater(str(self.prd_file))
        # This method prints, so just verify it doesn't crash
        updater.list_incomplete()

        # Verify by checking PRD state
        prd = updater.load_prd()
        incomplete = [s for s in prd['userStories'] if not s.get('passes')]

        self.assertEqual(len(incomplete), 2)  # US-001 and US-002

    def test_list_incomplete_all_complete(self):
        """Test listing when all stories complete."""
        # Mark all stories complete
        updater = PRDUpdater(str(self.prd_file))
        updater.mark_complete("US-001", "Done")
        updater.mark_complete("US-002", "Done")

        # List incomplete (should show "All complete!")
        updater.list_incomplete()

    def test_corrupted_json_handling(self):
        """Test handling of corrupted JSON file."""
        # Write invalid JSON
        with open(self.prd_file, 'w') as f:
            f.write("{ invalid json }")

        updater = PRDUpdater(str(self.prd_file))
        success = updater.mark_complete("US-001", "Test")

        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main(verbosity=2)
