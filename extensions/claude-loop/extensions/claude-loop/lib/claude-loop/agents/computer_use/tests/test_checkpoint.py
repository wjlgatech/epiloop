#!/usr/bin/env python3
"""
Tests for workflow checkpointing functionality.

Tests cover:
- CheckpointData creation and serialization
- WorkflowCheckpoint save/load operations
- Checkpoint listing and lookup
- Cleanup operations
- Resume from checkpoint scenarios
- Edge cases and error handling
"""

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from unittest import TestCase

from agents.computer_use.checkpoint import (
    CheckpointData,
    CheckpointInfo,
    WorkflowCheckpoint,
    cleanup_checkpoints,
    get_checkpoint_summary,
    list_checkpoints,
    load_latest_checkpoint,
)


class TestCheckpointData(TestCase):
    """Tests for CheckpointData dataclass."""

    def test_create_basic_checkpoint(self):
        """Test creating a basic CheckpointData."""
        data = CheckpointData(
            workflow_id="test_workflow",
            step_id="step_001",
            step_index=0,
            timestamp="2024-01-15T14:30:00",
        )

        self.assertEqual(data.workflow_id, "test_workflow")
        self.assertEqual(data.step_id, "step_001")
        self.assertEqual(data.step_index, 0)
        self.assertEqual(data.timestamp, "2024-01-15T14:30:00")
        self.assertEqual(data.context, {})
        self.assertEqual(data.metadata, {})

    def test_create_checkpoint_with_context(self):
        """Test creating CheckpointData with context."""
        context = {
            "project_path": "/path/to/project",
            "step_data": {"key": "value"},
            "nested": {"a": {"b": "c"}},
        }
        metadata = {"version": "1.0", "host": "localhost"}

        data = CheckpointData(
            workflow_id="test_workflow",
            step_id="step_001",
            step_index=0,
            timestamp="2024-01-15T14:30:00",
            context=context,
            metadata=metadata,
        )

        self.assertEqual(data.context, context)
        self.assertEqual(data.metadata, metadata)

    def test_to_dict(self):
        """Test converting CheckpointData to dictionary."""
        data = CheckpointData(
            workflow_id="test_workflow",
            step_id="step_001",
            step_index=0,
            timestamp="2024-01-15T14:30:00",
            context={"key": "value"},
        )

        as_dict = data.to_dict()

        self.assertIsInstance(as_dict, dict)
        self.assertEqual(as_dict["workflow_id"], "test_workflow")
        self.assertEqual(as_dict["step_id"], "step_001")
        self.assertEqual(as_dict["context"]["key"], "value")

    def test_from_dict(self):
        """Test creating CheckpointData from dictionary."""
        data_dict = {
            "workflow_id": "test_workflow",
            "step_id": "step_001",
            "step_index": 5,
            "timestamp": "2024-01-15T14:30:00",
            "context": {"key": "value"},
            "metadata": {"version": "1.0"},
        }

        data = CheckpointData.from_dict(data_dict)

        self.assertEqual(data.workflow_id, "test_workflow")
        self.assertEqual(data.step_id, "step_001")
        self.assertEqual(data.step_index, 5)
        self.assertEqual(data.context["key"], "value")
        self.assertEqual(data.metadata["version"], "1.0")

    def test_from_dict_missing_fields(self):
        """Test creating CheckpointData from incomplete dictionary."""
        data_dict: Dict[str, Any] = {}

        data = CheckpointData.from_dict(data_dict)

        self.assertEqual(data.workflow_id, "")
        self.assertEqual(data.step_id, "")
        self.assertEqual(data.step_index, 0)
        self.assertEqual(data.context, {})

    def test_roundtrip_serialization(self):
        """Test JSON serialization roundtrip."""
        original = CheckpointData(
            workflow_id="test_workflow",
            step_id="step_001",
            step_index=10,
            timestamp="2024-01-15T14:30:00",
            context={"nested": {"data": [1, 2, 3]}},
            metadata={"host": "test"},
        )

        # Serialize and deserialize
        json_str = json.dumps(original.to_dict())
        restored = CheckpointData.from_dict(json.loads(json_str))

        self.assertEqual(restored.workflow_id, original.workflow_id)
        self.assertEqual(restored.step_id, original.step_id)
        self.assertEqual(restored.step_index, original.step_index)
        self.assertEqual(restored.context, original.context)
        self.assertEqual(restored.metadata, original.metadata)


class TestWorkflowCheckpoint(TestCase):
    """Tests for WorkflowCheckpoint class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for checkpoints
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_workflow_checkpoint(self):
        """Test creating a WorkflowCheckpoint instance."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertEqual(checkpoint.workflow_id, "test_workflow")
        self.assertTrue(checkpoint.workflow_dir.exists())

    def test_sanitize_workflow_id(self):
        """Test workflow ID sanitization."""
        # Test with spaces and special characters
        checkpoint = WorkflowCheckpoint(
            workflow_id="my workflow/with:special!chars",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Should sanitize to safe characters
        self.assertEqual(checkpoint.workflow_id, "my_workflow_with_special_chars")

    def test_save_checkpoint(self):
        """Test saving a checkpoint."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        file_path = checkpoint.save(
            step_id="step_001",
            context={"project": "/path/to/project"},
        )

        self.assertTrue(file_path.exists())
        self.assertTrue(file_path.name.startswith("0000_"))
        self.assertTrue(file_path.name.endswith(".json"))

        # Verify content
        with open(file_path) as f:
            data = json.load(f)
        self.assertEqual(data["workflow_id"], "test_workflow")
        self.assertEqual(data["step_id"], "step_001")
        self.assertEqual(data["step_index"], 0)
        self.assertEqual(data["context"]["project"], "/path/to/project")

    def test_save_multiple_checkpoints(self):
        """Test saving multiple checkpoints in sequence."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Save 3 checkpoints
        for i in range(3):
            checkpoint.save(
                step_id=f"step_{i:03d}",
                context={"step_number": i},
            )

        # Verify step counter increments
        checkpoints = checkpoint.list_checkpoints()
        self.assertEqual(len(checkpoints), 3)
        self.assertEqual(checkpoints[0].step_index, 0)
        self.assertEqual(checkpoints[1].step_index, 1)
        self.assertEqual(checkpoints[2].step_index, 2)

    def test_has_checkpoint(self):
        """Test checking if checkpoints exist."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Initially no checkpoints
        self.assertFalse(checkpoint.has_checkpoint())

        # After saving
        checkpoint.save(step_id="step_001")
        self.assertTrue(checkpoint.has_checkpoint())

    def test_load_latest(self):
        """Test loading the latest checkpoint."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Save multiple checkpoints
        checkpoint.save(step_id="step_001", context={"data": 1})
        time.sleep(0.01)  # Ensure different timestamps
        checkpoint.save(step_id="step_002", context={"data": 2})
        time.sleep(0.01)
        checkpoint.save(step_id="step_003", context={"data": 3})

        # Load latest
        latest = checkpoint.load_latest()

        self.assertIsNotNone(latest)
        assert latest is not None  # Type narrowing for pyright
        self.assertEqual(latest.step_id, "step_003")
        self.assertEqual(latest.step_index, 2)
        self.assertEqual(latest.context["data"], 3)

    def test_load_by_step_id(self):
        """Test loading checkpoint by step ID."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint.save(step_id="step_001", context={"data": 1})
        checkpoint.save(step_id="step_002", context={"data": 2})
        checkpoint.save(step_id="step_003", context={"data": 3})

        # Load specific step
        step_2 = checkpoint.load_by_step_id("step_002")

        self.assertIsNotNone(step_2)
        assert step_2 is not None  # Type narrowing for pyright
        self.assertEqual(step_2.step_id, "step_002")
        self.assertEqual(step_2.context["data"], 2)

        # Non-existent step
        self.assertIsNone(checkpoint.load_by_step_id("non_existent"))

    def test_load_by_index(self):
        """Test loading checkpoint by step index."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint.save(step_id="step_001", context={"data": 1})
        checkpoint.save(step_id="step_002", context={"data": 2})
        checkpoint.save(step_id="step_003", context={"data": 3})

        # Load by index
        step_1 = checkpoint.load_by_index(1)

        self.assertIsNotNone(step_1)
        assert step_1 is not None  # Type narrowing for pyright
        self.assertEqual(step_1.step_id, "step_002")
        self.assertEqual(step_1.step_index, 1)

        # Non-existent index
        self.assertIsNone(checkpoint.load_by_index(99))

    def test_list_checkpoints(self):
        """Test listing all checkpoints."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint.save(step_id="step_001")
        checkpoint.save(step_id="step_002")
        checkpoint.save(step_id="step_003")

        checkpoints = checkpoint.list_checkpoints()

        self.assertEqual(len(checkpoints), 3)
        self.assertIsInstance(checkpoints[0], CheckpointInfo)
        self.assertEqual(checkpoints[0].step_id, "step_001")
        self.assertEqual(checkpoints[1].step_id, "step_002")
        self.assertEqual(checkpoints[2].step_id, "step_003")

    def test_get_next_step_index(self):
        """Test getting the next step index for resuming."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertEqual(checkpoint.get_next_step_index(), 0)

        checkpoint.save(step_id="step_001")
        self.assertEqual(checkpoint.get_next_step_index(), 1)

        checkpoint.save(step_id="step_002")
        self.assertEqual(checkpoint.get_next_step_index(), 2)

    def test_cleanup(self):
        """Test cleaning up all checkpoints."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint.save(step_id="step_001")
        checkpoint.save(step_id="step_002")
        checkpoint.save(step_id="step_003")

        self.assertEqual(len(checkpoint.list_checkpoints()), 3)

        checkpoint.cleanup()

        self.assertEqual(len(checkpoint.list_checkpoints()), 0)
        self.assertFalse(checkpoint.has_checkpoint())

    def test_cleanup_keep_latest(self):
        """Test cleanup while keeping the latest checkpoint."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint.save(step_id="step_001")
        checkpoint.save(step_id="step_002")
        checkpoint.save(step_id="step_003")

        checkpoint.cleanup(keep_latest=True)

        checkpoints = checkpoint.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0].step_id, "step_003")

    def test_cleanup_old(self):
        """Test cleaning up old checkpoints by age."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Save some checkpoints
        path1 = checkpoint.save(step_id="step_001")
        path2 = checkpoint.save(step_id="step_002")
        _ = checkpoint.save(step_id="step_003")  # Latest checkpoint

        # Artificially age the first two checkpoints
        old_time = time.time() - (2 * 3600)  # 2 hours ago
        path1.touch()
        import os
        os.utime(path1, (old_time, old_time))
        os.utime(path2, (old_time, old_time))

        # Cleanup checkpoints older than 1 hour
        checkpoint.cleanup_old(max_age_hours=1.0)

        checkpoints = checkpoint.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0].step_id, "step_003")

    def test_resume_workflow(self):
        """Test resuming a workflow from checkpoint."""
        # First run - save progress
        checkpoint1 = WorkflowCheckpoint(
            workflow_id="resumable_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        checkpoint1.save(step_id="setup", context={"status": "done"})
        checkpoint1.save(step_id="build", context={"status": "done"})
        checkpoint1.save(step_id="test", context={"status": "partial", "tests_passed": 5})

        # Simulate interruption and resume with new instance
        checkpoint2 = WorkflowCheckpoint(
            workflow_id="resumable_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertTrue(checkpoint2.has_checkpoint())

        # Load last checkpoint
        latest = checkpoint2.load_latest()
        assert latest is not None  # Type narrowing for pyright
        self.assertEqual(latest.step_id, "test")
        self.assertEqual(latest.context["tests_passed"], 5)

        # Continue from next step
        self.assertEqual(checkpoint2.get_next_step_index(), 3)

        # Save next step
        checkpoint2.save(step_id="deploy", context={"status": "done"})

        checkpoints = checkpoint2.list_checkpoints()
        self.assertEqual(len(checkpoints), 4)

    def test_multiple_workflows(self):
        """Test managing checkpoints for multiple workflows."""
        workflow1 = WorkflowCheckpoint(
            workflow_id="workflow_a",
            checkpoint_dir=self.checkpoint_dir,
        )
        workflow2 = WorkflowCheckpoint(
            workflow_id="workflow_b",
            checkpoint_dir=self.checkpoint_dir,
        )

        workflow1.save(step_id="step_001")
        workflow1.save(step_id="step_002")
        workflow2.save(step_id="step_001")

        self.assertEqual(len(workflow1.list_checkpoints()), 2)
        self.assertEqual(len(workflow2.list_checkpoints()), 1)

        # Cleanup only workflow1
        workflow1.cleanup()

        self.assertEqual(len(workflow1.list_checkpoints()), 0)
        self.assertEqual(len(workflow2.list_checkpoints()), 1)


class TestConvenienceFunctions(TestCase):
    """Tests for convenience functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_checkpoints_all_workflows(self):
        """Test listing checkpoints across all workflows."""
        # Create checkpoints for multiple workflows
        for i in range(3):
            workflow = WorkflowCheckpoint(
                workflow_id=f"workflow_{i}",
                checkpoint_dir=self.checkpoint_dir,
            )
            for j in range(2):
                workflow.save(step_id=f"step_{j}")

        result = list_checkpoints(self.checkpoint_dir)

        self.assertEqual(len(result), 3)
        self.assertIn("workflow_0", result)
        self.assertIn("workflow_1", result)
        self.assertIn("workflow_2", result)
        self.assertEqual(len(result["workflow_0"]), 2)

    def test_list_checkpoints_empty(self):
        """Test listing checkpoints when none exist."""
        result = list_checkpoints(self.checkpoint_dir)
        self.assertEqual(result, {})

    def test_load_latest_checkpoint(self):
        """Test loading latest checkpoint by workflow ID."""
        workflow = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )
        workflow.save(step_id="step_001")
        workflow.save(step_id="step_002")

        latest = load_latest_checkpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertIsNotNone(latest)
        assert latest is not None  # Type narrowing for pyright
        self.assertEqual(latest.step_id, "step_002")

    def test_load_latest_checkpoint_not_found(self):
        """Test loading latest checkpoint for non-existent workflow."""
        latest = load_latest_checkpoint(
            workflow_id="non_existent",
            checkpoint_dir=self.checkpoint_dir,
        )
        self.assertIsNone(latest)

    def test_cleanup_checkpoints_specific_workflow(self):
        """Test cleaning up checkpoints for a specific workflow."""
        # Create checkpoints for multiple workflows
        workflow1 = WorkflowCheckpoint(
            workflow_id="workflow_1",
            checkpoint_dir=self.checkpoint_dir,
        )
        workflow2 = WorkflowCheckpoint(
            workflow_id="workflow_2",
            checkpoint_dir=self.checkpoint_dir,
        )

        workflow1.save(step_id="step_001")
        workflow2.save(step_id="step_001")

        cleanup_checkpoints(
            workflow_id="workflow_1",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertEqual(len(workflow1.list_checkpoints()), 0)
        self.assertEqual(len(workflow2.list_checkpoints()), 1)

    def test_cleanup_checkpoints_all(self):
        """Test cleaning up all checkpoints."""
        # Create checkpoints for multiple workflows
        for i in range(3):
            workflow = WorkflowCheckpoint(
                workflow_id=f"workflow_{i}",
                checkpoint_dir=self.checkpoint_dir,
            )
            workflow.save(step_id="step_001")

        cleanup_checkpoints(checkpoint_dir=self.checkpoint_dir)

        result = list_checkpoints(self.checkpoint_dir)
        self.assertEqual(result, {})

    def test_get_checkpoint_summary(self):
        """Test getting checkpoint summary statistics."""
        # Create checkpoints for multiple workflows
        for i in range(2):
            workflow = WorkflowCheckpoint(
                workflow_id=f"workflow_{i}",
                checkpoint_dir=self.checkpoint_dir,
            )
            for j in range(3):
                workflow.save(step_id=f"step_{j}")

        summary = get_checkpoint_summary(self.checkpoint_dir)

        self.assertEqual(summary["total_workflows"], 2)
        self.assertEqual(summary["total_checkpoints"], 6)
        self.assertGreater(summary["total_size_bytes"], 0)
        self.assertIn("workflow_0", summary["workflows"])
        self.assertIn("workflow_1", summary["workflows"])
        self.assertEqual(summary["workflows"]["workflow_0"]["checkpoint_count"], 3)
        self.assertEqual(summary["workflows"]["workflow_0"]["latest_index"], 2)

    def test_get_checkpoint_summary_empty(self):
        """Test getting summary when no checkpoints exist."""
        summary = get_checkpoint_summary(self.checkpoint_dir)

        self.assertEqual(summary["total_workflows"], 0)
        self.assertEqual(summary["total_checkpoints"], 0)
        self.assertEqual(summary["workflows"], {})


class TestEdgeCases(TestCase):
    """Tests for edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_workflow_id(self):
        """Test handling empty workflow ID."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Should default to "workflow"
        self.assertEqual(checkpoint.workflow_id, "workflow")

    def test_step_id_with_special_chars(self):
        """Test saving checkpoint with special characters in step ID."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        file_path = checkpoint.save(
            step_id="step/with:special!chars",
            context={"data": "test"},
        )

        self.assertTrue(file_path.exists())

        # Should be able to load by original step ID
        loaded = checkpoint.load_by_step_id("step/with:special!chars")
        self.assertIsNotNone(loaded)
        assert loaded is not None  # Type narrowing for pyright
        self.assertEqual(loaded.step_id, "step/with:special!chars")

    def test_large_context(self):
        """Test saving checkpoint with large context."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        large_context = {
            "data": list(range(1000)),
            "nested": {f"key_{i}": f"value_{i}" for i in range(100)},
        }

        file_path = checkpoint.save(
            step_id="step_001",
            context=large_context,
        )

        self.assertTrue(file_path.exists())

        loaded = checkpoint.load_latest()
        assert loaded is not None  # Type narrowing for pyright
        self.assertEqual(loaded.context, large_context)

    def test_corrupted_checkpoint_file(self):
        """Test handling corrupted checkpoint file."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Save a valid checkpoint first
        checkpoint.save(step_id="step_001")
        checkpoint.save(step_id="step_002")

        # Corrupt the first (older) checkpoint file - files are named with index prefix
        # Format: {index:04d}_{step_id}_{timestamp}.json so step_001 sorts first
        checkpoint_files = sorted(checkpoint.workflow_dir.glob("*.json"))
        # Corrupt the first (older) checkpoint file, keeping the second (latest) intact
        with open(checkpoint_files[0], "w") as f:
            f.write("not valid json {{{")

        # Should still be able to list (skipping corrupted)
        # and load the valid checkpoint
        checkpoints = checkpoint.list_checkpoints()
        self.assertEqual(len(checkpoints), 1)  # Only valid one

        latest = checkpoint.load_latest()
        assert latest is not None  # Type narrowing for pyright
        self.assertEqual(latest.step_id, "step_002")

    def test_concurrent_saves(self):
        """Test saving checkpoints from same workflow ID in different instances."""
        # This simulates what might happen if workflow resumes
        checkpoint1 = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )
        checkpoint1.save(step_id="step_001")

        # New instance picks up from where we left off
        checkpoint2 = WorkflowCheckpoint(
            workflow_id="test_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        self.assertEqual(checkpoint2.get_next_step_index(), 1)

        checkpoint2.save(step_id="step_002")

        all_checkpoints = checkpoint2.list_checkpoints()
        self.assertEqual(len(all_checkpoints), 2)
        self.assertEqual(all_checkpoints[0].step_index, 0)
        self.assertEqual(all_checkpoints[1].step_index, 1)

    def test_cleanup_empty_workflow(self):
        """Test cleanup on workflow with no checkpoints."""
        checkpoint = WorkflowCheckpoint(
            workflow_id="empty_workflow",
            checkpoint_dir=self.checkpoint_dir,
        )

        # Should not raise
        checkpoint.cleanup()

        # Directory should be cleaned up
        self.assertFalse(checkpoint.workflow_dir.exists())


if __name__ == "__main__":
    import unittest
    unittest.main()
