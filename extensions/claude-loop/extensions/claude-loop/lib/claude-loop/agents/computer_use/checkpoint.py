#!/usr/bin/env python3
"""
checkpoint.py - Workflow Checkpointing for Long-Running Automation

This module provides checkpoint save/restore functionality for long-running
workflows in the computer_use automation system. Checkpoints are saved to
.claude-loop/checkpoints/ and can be used to resume workflows after interruption.

Usage:
    from agents.computer_use.checkpoint import (
        WorkflowCheckpoint,
        CheckpointData,
        list_checkpoints,
        load_latest_checkpoint,
        cleanup_checkpoints,
    )

    # Create checkpoint manager
    checkpoint = WorkflowCheckpoint(workflow_id="my_workflow")

    # Save checkpoint after each step
    checkpoint.save(
        step_id="step_001",
        context={"project_path": "/path/to/project", "step_data": {...}},
    )

    # Resume from checkpoint
    if checkpoint.has_checkpoint():
        data = checkpoint.load_latest()
        resume_from = data.step_id

    # Cleanup on successful completion
    checkpoint.cleanup()
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_CHECKPOINT_DIR = ".claude-loop/checkpoints"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CheckpointData:
    """Data stored in a checkpoint file.

    Attributes:
        workflow_id: Unique identifier for the workflow.
        step_id: Identifier of the completed step.
        step_index: Numeric index of the step (0-based).
        timestamp: ISO format timestamp when checkpoint was created.
        context: Arbitrary context data to restore state.
        metadata: Optional metadata (e.g., version, host info).
    """
    workflow_id: str
    step_id: str
    step_index: int
    timestamp: str
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Create CheckpointData from a dictionary.

        Args:
            data: Dictionary with checkpoint fields.

        Returns:
            CheckpointData instance.
        """
        return cls(
            workflow_id=data.get("workflow_id", ""),
            step_id=data.get("step_id", ""),
            step_index=data.get("step_index", 0),
            timestamp=data.get("timestamp", ""),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert CheckpointData to a dictionary.

        Returns:
            Dictionary representation of the checkpoint.
        """
        return asdict(self)


@dataclass
class CheckpointInfo:
    """Summary information about a checkpoint file.

    Attributes:
        file_path: Path to the checkpoint file.
        workflow_id: Workflow this checkpoint belongs to.
        step_id: The step ID stored in the checkpoint.
        step_index: The step index (0-based).
        created_at: When the checkpoint was created.
        file_size: Size of the checkpoint file in bytes.
    """
    file_path: Path
    workflow_id: str
    step_id: str
    step_index: int
    created_at: datetime
    file_size: int


# =============================================================================
# WorkflowCheckpoint Class
# =============================================================================


class WorkflowCheckpoint:
    """Manages checkpoint save/restore for a workflow.

    Checkpoints are saved as JSON files in the checkpoint directory,
    organized by workflow ID. Each checkpoint contains step information
    and arbitrary context data for state restoration.

    Checkpoint file naming convention:
        {workflow_id}/{step_index:04d}_{step_id}_{timestamp}.json

    Example:
        my_workflow/0001_setup_project_20240115_143022.json
    """

    def __init__(
        self,
        workflow_id: str,
        checkpoint_dir: Optional[Union[str, Path]] = None,
    ):
        """Initialize the WorkflowCheckpoint.

        Args:
            workflow_id: Unique identifier for this workflow.
            checkpoint_dir: Directory for checkpoints. Defaults to
                           .claude-loop/checkpoints/
        """
        self.workflow_id = self._sanitize_id(workflow_id)
        self.checkpoint_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
        self.workflow_dir = self.checkpoint_dir / self.workflow_id
        self._step_counter = 0

        # Create directories if needed
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

        # Initialize step counter from existing checkpoints
        self._init_step_counter()

    @staticmethod
    def _sanitize_id(identifier: str) -> str:
        """Sanitize an identifier for use in file paths.

        Args:
            identifier: The identifier to sanitize.

        Returns:
            Sanitized identifier (alphanumeric, underscores, dashes only).
        """
        # Replace spaces and special chars with underscores
        sanitized = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in identifier
        )
        # Remove consecutive underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        # Trim underscores from ends
        return sanitized.strip("_") or "workflow"

    def _init_step_counter(self):
        """Initialize step counter from existing checkpoints."""
        checkpoints = self._list_checkpoint_files()
        if checkpoints:
            # Get highest step index from existing checkpoints
            max_index = 0
            for cp_path in checkpoints:
                try:
                    data = self._load_checkpoint_file(cp_path)
                    if data and data.step_index > max_index:
                        max_index = data.step_index
                except Exception:
                    pass
            self._step_counter = max_index + 1

    def _list_checkpoint_files(self) -> List[Path]:
        """List all checkpoint files for this workflow.

        Returns:
            List of checkpoint file paths, sorted by name (oldest first).
        """
        if not self.workflow_dir.exists():
            return []

        files = list(self.workflow_dir.glob("*.json"))
        return sorted(files, key=lambda p: p.name)

    def _load_checkpoint_file(self, file_path: Path) -> Optional[CheckpointData]:
        """Load a checkpoint from a file.

        Args:
            file_path: Path to the checkpoint file.

        Returns:
            CheckpointData if successful, None otherwise.
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return CheckpointData.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint {file_path}: {e}")
            return None

    def save(
        self,
        step_id: str,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Save a checkpoint after completing a step.

        Args:
            step_id: Identifier for the completed step.
            context: Arbitrary context data to save for restoration.
            metadata: Optional metadata (version, host, etc.).

        Returns:
            Path to the saved checkpoint file.
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Sanitize step_id for filename
        safe_step_id = self._sanitize_id(step_id)

        # Create checkpoint data
        checkpoint = CheckpointData(
            workflow_id=self.workflow_id,
            step_id=step_id,
            step_index=self._step_counter,
            timestamp=timestamp.isoformat(),
            context=context or {},
            metadata=metadata or {},
        )

        # Generate filename
        filename = f"{self._step_counter:04d}_{safe_step_id}_{timestamp_str}.json"
        file_path = self.workflow_dir / filename

        # Write checkpoint file
        with open(file_path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, default=str)

        logger.info(f"Checkpoint saved: {file_path}")

        # Increment step counter for next save
        self._step_counter += 1

        return file_path

    def has_checkpoint(self) -> bool:
        """Check if any checkpoints exist for this workflow.

        Returns:
            True if at least one checkpoint exists.
        """
        return len(self._list_checkpoint_files()) > 0

    def load_latest(self) -> Optional[CheckpointData]:
        """Load the most recent checkpoint.

        Returns:
            CheckpointData for the latest checkpoint, or None if no checkpoints.
        """
        checkpoint_files = self._list_checkpoint_files()
        if not checkpoint_files:
            return None

        # Get the last file (highest step index/timestamp)
        latest_file = checkpoint_files[-1]
        return self._load_checkpoint_file(latest_file)

    def load_by_step_id(self, step_id: str) -> Optional[CheckpointData]:
        """Load a checkpoint by step ID.

        Args:
            step_id: The step ID to find.

        Returns:
            CheckpointData if found, None otherwise.
        """
        for cp_file in self._list_checkpoint_files():
            data = self._load_checkpoint_file(cp_file)
            if data and data.step_id == step_id:
                return data
        return None

    def load_by_index(self, step_index: int) -> Optional[CheckpointData]:
        """Load a checkpoint by step index.

        Args:
            step_index: The step index to find (0-based).

        Returns:
            CheckpointData if found, None otherwise.
        """
        for cp_file in self._list_checkpoint_files():
            data = self._load_checkpoint_file(cp_file)
            if data and data.step_index == step_index:
                return data
        return None

    def list_checkpoints(self) -> List[CheckpointInfo]:
        """List all checkpoints for this workflow.

        Returns:
            List of CheckpointInfo objects, sorted by step index.
        """
        result = []
        for cp_file in self._list_checkpoint_files():
            try:
                data = self._load_checkpoint_file(cp_file)
                if data:
                    # Parse timestamp from the checkpoint data
                    try:
                        created_at = datetime.fromisoformat(data.timestamp)
                    except ValueError:
                        created_at = datetime.fromtimestamp(cp_file.stat().st_mtime)

                    info = CheckpointInfo(
                        file_path=cp_file,
                        workflow_id=data.workflow_id,
                        step_id=data.step_id,
                        step_index=data.step_index,
                        created_at=created_at,
                        file_size=cp_file.stat().st_size,
                    )
                    result.append(info)
            except Exception as e:
                logger.warning(f"Failed to get info for checkpoint {cp_file}: {e}")

        return sorted(result, key=lambda x: x.step_index)

    def get_next_step_index(self) -> int:
        """Get the next step index (for resuming).

        Returns:
            The step index that would be used for the next checkpoint.
        """
        return self._step_counter

    def cleanup(self, keep_latest: bool = False):
        """Remove all checkpoints for this workflow.

        Call this after successful workflow completion.

        Args:
            keep_latest: If True, keep the latest checkpoint as a record.
        """
        checkpoint_files = self._list_checkpoint_files()

        if keep_latest and checkpoint_files:
            # Keep the last checkpoint
            checkpoint_files = checkpoint_files[:-1]

        for cp_file in checkpoint_files:
            try:
                cp_file.unlink()
                logger.debug(f"Removed checkpoint: {cp_file}")
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint {cp_file}: {e}")

        # Remove workflow directory if empty
        if self.workflow_dir.exists():
            try:
                # Only remove if empty
                if not any(self.workflow_dir.iterdir()):
                    self.workflow_dir.rmdir()
                    logger.info(f"Removed empty checkpoint directory: {self.workflow_dir}")
            except Exception as e:
                logger.debug(f"Could not remove workflow directory: {e}")

        logger.info(f"Cleanup complete for workflow '{self.workflow_id}'")

    def cleanup_old(self, max_age_hours: float = 24.0):
        """Remove checkpoints older than the specified age.

        Args:
            max_age_hours: Maximum age in hours. Checkpoints older than this
                          will be removed.
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0

        for cp_file in self._list_checkpoint_files():
            try:
                if cp_file.stat().st_mtime < cutoff_time:
                    cp_file.unlink()
                    removed_count += 1
                    logger.debug(f"Removed old checkpoint: {cp_file}")
            except Exception as e:
                logger.warning(f"Failed to remove old checkpoint {cp_file}: {e}")

        if removed_count > 0:
            logger.info(f"Removed {removed_count} old checkpoint(s) for workflow '{self.workflow_id}'")

    def __repr__(self) -> str:
        checkpoints = self._list_checkpoint_files()
        return f"WorkflowCheckpoint(workflow_id='{self.workflow_id}', checkpoints={len(checkpoints)})"


# =============================================================================
# Convenience Functions
# =============================================================================


def list_checkpoints(
    checkpoint_dir: Optional[Union[str, Path]] = None
) -> Dict[str, List[CheckpointInfo]]:
    """List all checkpoints across all workflows.

    Args:
        checkpoint_dir: Directory containing checkpoints. Defaults to
                       .claude-loop/checkpoints/

    Returns:
        Dictionary mapping workflow_id to list of CheckpointInfo objects.
    """
    checkpoint_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)

    if not checkpoint_dir.exists():
        return {}

    result: Dict[str, List[CheckpointInfo]] = {}

    # Iterate through workflow directories
    for workflow_dir in checkpoint_dir.iterdir():
        if workflow_dir.is_dir():
            workflow_id = workflow_dir.name
            checkpoint = WorkflowCheckpoint(
                workflow_id=workflow_id,
                checkpoint_dir=checkpoint_dir,
            )
            checkpoints = checkpoint.list_checkpoints()
            if checkpoints:
                result[workflow_id] = checkpoints

    return result


def load_latest_checkpoint(
    workflow_id: str,
    checkpoint_dir: Optional[Union[str, Path]] = None,
) -> Optional[CheckpointData]:
    """Load the latest checkpoint for a workflow.

    Args:
        workflow_id: The workflow ID to load checkpoint for.
        checkpoint_dir: Directory containing checkpoints. Defaults to
                       .claude-loop/checkpoints/

    Returns:
        CheckpointData if found, None otherwise.
    """
    checkpoint = WorkflowCheckpoint(
        workflow_id=workflow_id,
        checkpoint_dir=checkpoint_dir,
    )
    return checkpoint.load_latest()


def cleanup_checkpoints(
    workflow_id: Optional[str] = None,
    checkpoint_dir: Optional[Union[str, Path]] = None,
    max_age_hours: Optional[float] = None,
):
    """Clean up checkpoints.

    Args:
        workflow_id: If specified, only clean up this workflow.
                    If None, clean up all workflows.
        checkpoint_dir: Directory containing checkpoints. Defaults to
                       .claude-loop/checkpoints/
        max_age_hours: If specified, only remove checkpoints older than this.
                      If None, remove all checkpoints.
    """
    checkpoint_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)

    if not checkpoint_dir.exists():
        return

    if workflow_id:
        # Clean up specific workflow
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            checkpoint_dir=checkpoint_dir,
        )
        if max_age_hours is not None:
            checkpoint.cleanup_old(max_age_hours=max_age_hours)
        else:
            checkpoint.cleanup()
    else:
        # Clean up all workflows
        for workflow_dir in checkpoint_dir.iterdir():
            if workflow_dir.is_dir():
                checkpoint = WorkflowCheckpoint(
                    workflow_id=workflow_dir.name,
                    checkpoint_dir=checkpoint_dir,
                )
                if max_age_hours is not None:
                    checkpoint.cleanup_old(max_age_hours=max_age_hours)
                else:
                    checkpoint.cleanup()

        # Try to remove the main checkpoint directory if empty
        try:
            if checkpoint_dir.exists() and not any(checkpoint_dir.iterdir()):
                checkpoint_dir.rmdir()
                logger.info(f"Removed empty checkpoint directory: {checkpoint_dir}")
        except Exception:
            pass


def get_checkpoint_summary(
    checkpoint_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Get a summary of all checkpoints.

    Args:
        checkpoint_dir: Directory containing checkpoints. Defaults to
                       .claude-loop/checkpoints/

    Returns:
        Dictionary with summary statistics.
    """
    all_checkpoints = list_checkpoints(checkpoint_dir)

    total_checkpoints = sum(len(cps) for cps in all_checkpoints.values())
    total_size = sum(
        cp.file_size
        for cps in all_checkpoints.values()
        for cp in cps
    )

    # Find oldest and newest
    oldest = None
    newest = None
    for cps in all_checkpoints.values():
        for cp in cps:
            if oldest is None or cp.created_at < oldest:
                oldest = cp.created_at
            if newest is None or cp.created_at > newest:
                newest = cp.created_at

    return {
        "total_workflows": len(all_checkpoints),
        "total_checkpoints": total_checkpoints,
        "total_size_bytes": total_size,
        "workflows": {
            wf_id: {
                "checkpoint_count": len(cps),
                "latest_step": cps[-1].step_id if cps else None,
                "latest_index": cps[-1].step_index if cps else None,
            }
            for wf_id, cps in all_checkpoints.items()
        },
        "oldest_checkpoint": oldest.isoformat() if oldest else None,
        "newest_checkpoint": newest.isoformat() if newest else None,
    }


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Main class
    "WorkflowCheckpoint",
    # Data classes
    "CheckpointData",
    "CheckpointInfo",
    # Convenience functions
    "list_checkpoints",
    "load_latest_checkpoint",
    "cleanup_checkpoints",
    "get_checkpoint_summary",
    # Constants
    "DEFAULT_CHECKPOINT_DIR",
]
