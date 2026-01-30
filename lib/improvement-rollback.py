#!/usr/bin/env python3
"""
improvement-rollback.py - Rollback Mechanism for claude-loop Improvements

Provides rollback capabilities for improvements that cause regressions. Tracks
git commits associated with each improvement and enables safe reversion.

Features:
- Track git commits associated with each improvement
- Rollback all commits from an improvement branch
- Re-run validation suite after rollback
- Update capability inventory to reflect rollback
- Mark improvement as 'rolled_back' with reason
- Keep rollback history for analysis

Usage:
    python lib/improvement-rollback.py rollback <prd_name>
    python lib/improvement-rollback.py rollback <prd_name> --reason "..."
    python lib/improvement-rollback.py rollback <prd_name> --dry-run
    python lib/improvement-rollback.py status <prd_name>
    python lib/improvement-rollback.py history
    python lib/improvement-rollback.py commits <prd_name>
    python lib/improvement-rollback.py track <prd_name> <commit_sha>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Data Classes
# ============================================================================

class RollbackStatus(Enum):
    """Status of a rollback operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CommitInfo:
    """Information about a tracked commit."""

    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha": self.sha,
            "message": self.message,
            "author": self.author,
            "date": self.date,
            "files_changed": self.files_changed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CommitInfo:
        return cls(
            sha=data.get("sha", ""),
            message=data.get("message", ""),
            author=data.get("author", ""),
            date=data.get("date", ""),
            files_changed=data.get("files_changed", []),
        )


@dataclass
class ValidationAfterRollback:
    """Result of validation after rollback."""

    ran: bool = False
    passed: bool = False
    test_results: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ran": self.ran,
            "passed": self.passed,
            "test_results": self.test_results,
            "error": self.error,
        }


@dataclass
class RollbackResult:
    """Complete result of a rollback operation."""

    prd_name: str
    status: str  # success, partial, failed, skipped
    rolled_back_at: str
    reason: str

    # Commit information
    commits_tracked: int = 0
    commits_reverted: int = 0
    commits_failed: list[str] = field(default_factory=list)
    revert_commits: list[str] = field(default_factory=list)

    # Branch information
    original_branch: str = ""
    improvement_branch: str = ""
    branch_deleted: bool = False

    # Validation
    validation: ValidationAfterRollback = field(default_factory=ValidationAfterRollback)

    # Inventory update
    inventory_updated: bool = False
    capabilities_reverted: list[str] = field(default_factory=list)

    # Error details
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_name": self.prd_name,
            "status": self.status,
            "rolled_back_at": self.rolled_back_at,
            "reason": self.reason,
            "commits_tracked": self.commits_tracked,
            "commits_reverted": self.commits_reverted,
            "commits_failed": self.commits_failed,
            "revert_commits": self.revert_commits,
            "original_branch": self.original_branch,
            "improvement_branch": self.improvement_branch,
            "branch_deleted": self.branch_deleted,
            "validation": self.validation.to_dict(),
            "inventory_updated": self.inventory_updated,
            "capabilities_reverted": self.capabilities_reverted,
            "error_message": self.error_message,
            "warnings": self.warnings,
        }


@dataclass
class ImprovementCommitTracking:
    """Tracking data for commits associated with an improvement."""

    prd_name: str
    branch_name: str
    base_commit: str  # Commit SHA before improvement started
    commits: list[CommitInfo] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    status: str = "in_progress"  # in_progress, complete, rolled_back

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_name": self.prd_name,
            "branch_name": self.branch_name,
            "base_commit": self.base_commit,
            "commits": [c.to_dict() for c in self.commits],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImprovementCommitTracking:
        return cls(
            prd_name=data.get("prd_name", ""),
            branch_name=data.get("branch_name", ""),
            base_commit=data.get("base_commit", ""),
            commits=[CommitInfo.from_dict(c) for c in data.get("commits", [])],
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            status=data.get("status", "in_progress"),
        )


@dataclass
class RollbackHistoryEntry:
    """An entry in the rollback history."""

    prd_name: str
    rolled_back_at: str
    reason: str
    status: str
    commits_reverted: int
    validation_passed: bool
    rolled_back_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_name": self.prd_name,
            "rolled_back_at": self.rolled_back_at,
            "reason": self.reason,
            "status": self.status,
            "commits_reverted": self.commits_reverted,
            "validation_passed": self.validation_passed,
            "rolled_back_by": self.rolled_back_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RollbackHistoryEntry:
        return cls(
            prd_name=data.get("prd_name", ""),
            rolled_back_at=data.get("rolled_back_at", ""),
            reason=data.get("reason", ""),
            status=data.get("status", ""),
            commits_reverted=data.get("commits_reverted", 0),
            validation_passed=data.get("validation_passed", False),
            rolled_back_by=data.get("rolled_back_by", ""),
        )


# ============================================================================
# Improvement Rollback Manager
# ============================================================================

class ImprovementRollback:
    """
    Manages rollback of improvement PRDs.

    Tracks commits associated with improvements and provides safe
    rollback capabilities with validation and inventory updates.
    """

    def __init__(
        self,
        project_root: Path | None = None,
    ):
        """
        Initialize the rollback manager.

        Args:
            project_root: Path to project root
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.claude_loop_dir = self.project_root / ".claude-loop"
        self.improvements_dir = self.claude_loop_dir / "improvements"
        self.tracking_file = self.claude_loop_dir / "improvement_commits.json"
        self.rollback_history_file = self.claude_loop_dir / "rollback_history.jsonl"

        # Ensure directories exist
        self.claude_loop_dir.mkdir(parents=True, exist_ok=True)
        self.improvements_dir.mkdir(parents=True, exist_ok=True)

    def _load_tracking_data(self) -> dict[str, ImprovementCommitTracking]:
        """Load tracking data from file."""
        if not self.tracking_file.exists():
            return {}

        try:
            with open(self.tracking_file) as f:
                data = json.load(f)
                return {
                    prd_name: ImprovementCommitTracking.from_dict(tracking_data)
                    for prd_name, tracking_data in data.items()
                }
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_tracking_data(self, data: dict[str, ImprovementCommitTracking]) -> None:
        """Save tracking data to file."""
        try:
            with open(self.tracking_file, "w") as f:
                json.dump(
                    {prd_name: tracking.to_dict() for prd_name, tracking in data.items()},
                    f,
                    indent=2,
                )
        except IOError as e:
            print(f"Warning: Could not save tracking data: {e}", file=sys.stderr)

    def _run_git_command(
        self,
        args: list[str],
        check: bool = True,
    ) -> tuple[int, str, str]:
        """
        Run a git command and return output.

        Args:
            args: Git command arguments (without 'git' prefix)
            check: Whether to raise on non-zero exit

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except Exception as e:
            return -2, "", str(e)

    def _get_current_branch(self) -> str:
        """Get the current git branch name."""
        exit_code, stdout, _ = self._run_git_command(["branch", "--show-current"])
        return stdout if exit_code == 0 else ""

    def _get_current_commit(self) -> str:
        """Get the current HEAD commit SHA."""
        exit_code, stdout, _ = self._run_git_command(["rev-parse", "HEAD"])
        return stdout if exit_code == 0 else ""

    def _get_commit_info(self, sha: str) -> CommitInfo | None:
        """Get detailed information about a commit."""
        # Get commit message and author
        exit_code, stdout, _ = self._run_git_command([
            "log", "-1", "--format=%H%n%s%n%an%n%ai", sha
        ])
        if exit_code != 0:
            return None

        lines = stdout.split("\n")
        if len(lines) < 4:
            return None

        # Get files changed
        exit_code, files_stdout, _ = self._run_git_command([
            "diff-tree", "--no-commit-id", "--name-only", "-r", sha
        ])
        files = files_stdout.split("\n") if exit_code == 0 and files_stdout else []

        return CommitInfo(
            sha=lines[0],
            message=lines[1],
            author=lines[2],
            date=lines[3],
            files_changed=[f for f in files if f],
        )

    def track_improvement_start(
        self,
        prd_name: str,
        branch_name: str,
    ) -> bool:
        """
        Start tracking commits for an improvement.

        Args:
            prd_name: Name of the improvement PRD
            branch_name: Git branch for the improvement

        Returns:
            True if tracking started successfully
        """
        tracking_data = self._load_tracking_data()

        base_commit = self._get_current_commit()
        if not base_commit:
            return False

        tracking = ImprovementCommitTracking(
            prd_name=prd_name,
            branch_name=branch_name,
            base_commit=base_commit,
            started_at=datetime.now().isoformat(),
            status="in_progress",
        )

        tracking_data[prd_name] = tracking
        self._save_tracking_data(tracking_data)

        return True

    def track_commit(
        self,
        prd_name: str,
        commit_sha: str,
    ) -> bool:
        """
        Track a commit for an improvement.

        Args:
            prd_name: Name of the improvement PRD
            commit_sha: SHA of the commit to track

        Returns:
            True if commit was tracked
        """
        tracking_data = self._load_tracking_data()

        if prd_name not in tracking_data:
            # Create new tracking entry if not exists
            branch = self._get_current_branch()
            if not self.track_improvement_start(prd_name, branch):
                return False
            tracking_data = self._load_tracking_data()

        commit_info = self._get_commit_info(commit_sha)
        if not commit_info:
            return False

        # Check if already tracked
        existing_shas = [c.sha for c in tracking_data[prd_name].commits]
        if commit_sha in existing_shas:
            return True  # Already tracked

        tracking_data[prd_name].commits.append(commit_info)
        self._save_tracking_data(tracking_data)

        return True

    def track_improvement_complete(self, prd_name: str) -> bool:
        """
        Mark an improvement as complete (no more commits expected).

        Args:
            prd_name: Name of the improvement PRD

        Returns:
            True if marked complete
        """
        tracking_data = self._load_tracking_data()

        if prd_name not in tracking_data:
            return False

        tracking_data[prd_name].completed_at = datetime.now().isoformat()
        tracking_data[prd_name].status = "complete"
        self._save_tracking_data(tracking_data)

        return True

    def get_tracked_commits(self, prd_name: str) -> list[CommitInfo]:
        """
        Get all commits tracked for an improvement.

        Args:
            prd_name: Name of the improvement PRD

        Returns:
            List of tracked commits
        """
        tracking_data = self._load_tracking_data()
        if prd_name not in tracking_data:
            return []
        return tracking_data[prd_name].commits

    def get_tracking_status(self, prd_name: str) -> dict[str, Any] | None:
        """
        Get tracking status for an improvement.

        Args:
            prd_name: Name of the improvement PRD

        Returns:
            Tracking status dict or None if not tracked
        """
        tracking_data = self._load_tracking_data()
        if prd_name not in tracking_data:
            return None
        return tracking_data[prd_name].to_dict()

    def _revert_commit(self, commit_sha: str) -> tuple[bool, str]:
        """
        Revert a single commit.

        Args:
            commit_sha: SHA of commit to revert

        Returns:
            Tuple of (success, revert_commit_sha or error_message)
        """
        # Try to revert the commit
        exit_code, stdout, stderr = self._run_git_command([
            "revert", "--no-edit", commit_sha
        ])

        if exit_code == 0:
            # Get the revert commit SHA
            revert_sha = self._get_current_commit()
            return True, revert_sha

        # Check if revert failed due to conflicts
        if "conflict" in stderr.lower():
            # Abort the revert
            self._run_git_command(["revert", "--abort"])
            return False, f"Conflict reverting {commit_sha}: {stderr}"

        return False, f"Failed to revert {commit_sha}: {stderr}"

    def _run_validation(self) -> ValidationAfterRollback:
        """
        Run the validation suite after rollback.

        Returns:
            ValidationAfterRollback result
        """
        result = ValidationAfterRollback()

        # Check if validator exists
        validator_path = self.project_root / "lib" / "improvement-validator.py"
        if not validator_path.exists():
            result.error = "Validator not found"
            return result

        try:
            # Run existing test suite check
            validation_result = subprocess.run(
                ["python3", str(validator_path), "check-tests"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300,
            )

            result.ran = True
            result.passed = validation_result.returncode == 0
            result.test_results = {
                "exit_code": validation_result.returncode,
                "stdout": validation_result.stdout[:1000] if validation_result.stdout else "",
                "stderr": validation_result.stderr[:500] if validation_result.stderr else "",
            }

        except subprocess.TimeoutExpired:
            result.ran = True
            result.passed = False
            result.error = "Validation timed out after 300 seconds"
        except Exception as e:
            result.ran = False
            result.error = str(e)

        return result

    def _update_capability_inventory(
        self,
        prd_name: str,
        rolled_back: bool,
    ) -> tuple[bool, list[str]]:
        """
        Update the capability inventory after rollback.

        Args:
            prd_name: Name of the PRD being rolled back
            rolled_back: Whether rollback was successful

        Returns:
            Tuple of (success, list of reverted capabilities)
        """
        reverted_caps = []

        # Load the PRD to get capabilities that were added
        prd_path = self.improvements_dir / f"{prd_name}.json"
        if not prd_path.exists():
            return False, []

        try:
            prd_data = json.loads(prd_path.read_text())
        except json.JSONDecodeError:
            return False, []

        # Check for capability inventory
        inventory_path = self.claude_loop_dir / "capability_inventory.json"
        if not inventory_path.exists():
            return True, []  # No inventory to update

        try:
            inventory = json.loads(inventory_path.read_text())
        except json.JSONDecodeError:
            return False, []

        # Mark capabilities from this improvement as limited/unavailable
        capabilities = inventory.get("capabilities", {})

        # Get file scope from PRD to identify related capabilities
        file_scopes = []
        for story in prd_data.get("userStories", []):
            file_scopes.extend(story.get("fileScope", []))

        # Find capabilities related to these files
        for cap_id, cap_data in capabilities.items():
            source_name = cap_data.get("source_name", "")
            # Check if capability source matches any file scope
            for scope in file_scopes:
                if scope in source_name or source_name in scope:
                    # Mark as limited due to rollback
                    cap_data["status"] = "limited"
                    cap_data["limitations"] = f"Rolled back from improvement: {prd_name}"
                    cap_data["last_checked"] = datetime.now().isoformat()
                    reverted_caps.append(cap_id)
                    break

        # Save updated inventory
        inventory["capabilities"] = capabilities
        inventory["updated_at"] = datetime.now().isoformat()

        try:
            with open(inventory_path, "w") as f:
                json.dump(inventory, f, indent=2)
            return True, reverted_caps
        except IOError:
            return False, reverted_caps

    def _update_prd_status(
        self,
        prd_name: str,
        reason: str,
    ) -> bool:
        """
        Update the PRD status to rolled_back.

        Args:
            prd_name: Name of the PRD
            reason: Reason for rollback

        Returns:
            True if updated successfully
        """
        prd_path = self.improvements_dir / f"{prd_name}.json"
        if not prd_path.exists():
            return False

        try:
            prd_data = json.loads(prd_path.read_text())
            prd_data["status"] = "rolled_back"
            prd_data["rollback_reason"] = reason
            prd_data["rolled_back_at"] = datetime.now().isoformat()

            with open(prd_path, "w") as f:
                json.dump(prd_data, f, indent=2)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def _update_tracking_status(self, prd_name: str, status: str) -> bool:
        """Update the tracking status for an improvement."""
        tracking_data = self._load_tracking_data()
        if prd_name not in tracking_data:
            return False

        tracking_data[prd_name].status = status
        self._save_tracking_data(tracking_data)
        return True

    def _log_rollback_history(self, result: RollbackResult) -> None:
        """Log rollback to history file."""
        entry = RollbackHistoryEntry(
            prd_name=result.prd_name,
            rolled_back_at=result.rolled_back_at,
            reason=result.reason,
            status=result.status,
            commits_reverted=result.commits_reverted,
            validation_passed=result.validation.passed if result.validation.ran else False,
        )

        try:
            with open(self.rollback_history_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except IOError as e:
            print(f"Warning: Could not log rollback history: {e}", file=sys.stderr)

    def rollback_improvement(
        self,
        prd_name: str,
        reason: str = "",
        dry_run: bool = False,
        skip_validation: bool = False,
    ) -> RollbackResult:
        """
        Rollback an improvement by reverting all its commits.

        Args:
            prd_name: Name of the improvement PRD to rollback
            reason: Reason for the rollback
            dry_run: If True, show what would happen without making changes
            skip_validation: If True, skip post-rollback validation

        Returns:
            RollbackResult with details of the operation
        """
        result = RollbackResult(
            prd_name=prd_name,
            status=RollbackStatus.FAILED.value,
            rolled_back_at=datetime.now().isoformat(),
            reason=reason or "No reason provided",
        )

        # Get tracking data
        tracking_data = self._load_tracking_data()
        if prd_name not in tracking_data:
            result.error_message = f"No commit tracking found for improvement: {prd_name}"
            result.status = RollbackStatus.SKIPPED.value
            return result

        tracking = tracking_data[prd_name]
        result.commits_tracked = len(tracking.commits)
        result.improvement_branch = tracking.branch_name
        result.original_branch = self._get_current_branch()

        if result.commits_tracked == 0:
            result.error_message = "No commits tracked for this improvement"
            result.status = RollbackStatus.SKIPPED.value
            return result

        if tracking.status == "rolled_back":
            result.error_message = "Improvement already rolled back"
            result.status = RollbackStatus.SKIPPED.value
            return result

        # Dry run - just show what would happen
        if dry_run:
            result.status = RollbackStatus.SKIPPED.value
            result.warnings.append("DRY RUN - no changes made")
            result.warnings.append(f"Would revert {len(tracking.commits)} commits")
            for commit in reversed(tracking.commits):
                result.warnings.append(f"  - {commit.sha[:8]}: {commit.message}")
            return result

        # Revert commits in reverse order (newest first)
        for commit in reversed(tracking.commits):
            success, revert_result = self._revert_commit(commit.sha)
            if success:
                result.commits_reverted += 1
                result.revert_commits.append(revert_result)
            else:
                result.commits_failed.append(commit.sha)
                result.warnings.append(f"Failed to revert {commit.sha}: {revert_result}")

        # Determine overall status
        if result.commits_reverted == result.commits_tracked:
            result.status = RollbackStatus.SUCCESS.value
        elif result.commits_reverted > 0:
            result.status = RollbackStatus.PARTIAL.value
        else:
            result.status = RollbackStatus.FAILED.value

        # Run validation unless skipped or rollback failed
        if not skip_validation and result.status != RollbackStatus.FAILED.value:
            result.validation = self._run_validation()
            if not result.validation.passed:
                result.warnings.append("Post-rollback validation failed")

        # Update capability inventory
        if result.status != RollbackStatus.FAILED.value:
            inv_success, reverted_caps = self._update_capability_inventory(prd_name, True)
            result.inventory_updated = inv_success
            result.capabilities_reverted = reverted_caps

        # Update PRD status
        if result.status != RollbackStatus.FAILED.value:
            self._update_prd_status(prd_name, result.reason)

        # Update tracking status
        if result.status == RollbackStatus.SUCCESS.value:
            self._update_tracking_status(prd_name, "rolled_back")
        elif result.status == RollbackStatus.PARTIAL.value:
            self._update_tracking_status(prd_name, "partial_rollback")

        # Log to history
        self._log_rollback_history(result)

        return result

    def get_rollback_history(self, limit: int = 50) -> list[RollbackHistoryEntry]:
        """
        Get rollback history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of rollback history entries (newest first)
        """
        if not self.rollback_history_file.exists():
            return []

        entries = []
        try:
            with open(self.rollback_history_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            entries.append(RollbackHistoryEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue
        except IOError:
            return []

        # Return newest first
        entries.reverse()
        return entries[:limit]

    def list_all_tracked(self) -> list[dict[str, Any]]:
        """
        List all tracked improvements.

        Returns:
            List of tracking summaries
        """
        tracking_data = self._load_tracking_data()

        summaries = []
        for prd_name, tracking in tracking_data.items():
            summaries.append({
                "prd_name": prd_name,
                "branch_name": tracking.branch_name,
                "commit_count": len(tracking.commits),
                "status": tracking.status,
                "started_at": tracking.started_at,
                "completed_at": tracking.completed_at,
            })

        return summaries


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Rollback Mechanism for claude-loop Improvements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/improvement-rollback.py rollback improve-file-handling-abc123
    python lib/improvement-rollback.py rollback improve-ui-xyz --reason "Caused test failures"
    python lib/improvement-rollback.py rollback improve-net-456 --dry-run
    python lib/improvement-rollback.py status improve-file-handling-abc123
    python lib/improvement-rollback.py commits improve-file-handling-abc123
    python lib/improvement-rollback.py track improve-file-handling-abc123 abc1234
    python lib/improvement-rollback.py history
    python lib/improvement-rollback.py list
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # rollback command
    rollback_parser = subparsers.add_parser(
        "rollback", help="Rollback an improvement"
    )
    rollback_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD to rollback",
    )
    rollback_parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Reason for the rollback",
    )
    rollback_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes",
    )
    rollback_parser.add_argument(
        "--skip-validation", action="store_true",
        help="Skip post-rollback validation",
    )
    rollback_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # status command
    status_parser = subparsers.add_parser(
        "status", help="Show tracking status for an improvement"
    )
    status_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD",
    )
    status_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # commits command
    commits_parser = subparsers.add_parser(
        "commits", help="List commits tracked for an improvement"
    )
    commits_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD",
    )
    commits_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # track command
    track_parser = subparsers.add_parser(
        "track", help="Track a commit for an improvement"
    )
    track_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD",
    )
    track_parser.add_argument(
        "commit_sha",
        type=str,
        help="SHA of the commit to track",
    )

    # start-tracking command
    start_parser = subparsers.add_parser(
        "start-tracking", help="Start tracking commits for an improvement"
    )
    start_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD",
    )
    start_parser.add_argument(
        "--branch",
        type=str,
        default="",
        help="Branch name (defaults to current branch)",
    )

    # complete-tracking command
    complete_parser = subparsers.add_parser(
        "complete-tracking", help="Mark improvement as complete (no more commits)"
    )
    complete_parser.add_argument(
        "prd_name",
        type=str,
        help="Name of the improvement PRD",
    )

    # history command
    history_parser = subparsers.add_parser(
        "history", help="Show rollback history"
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of entries to show (default: 20)",
    )
    history_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List all tracked improvements"
    )
    list_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize rollback manager
    project_root = Path(__file__).parent.parent
    rollback_mgr = ImprovementRollback(project_root=project_root)

    if args.command == "rollback":
        result = rollback_mgr.rollback_improvement(
            prd_name=args.prd_name,
            reason=args.reason,
            dry_run=args.dry_run,
            skip_validation=args.skip_validation,
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"ROLLBACK {'(DRY RUN) ' if args.dry_run else ''}REPORT")
            print(f"{'='*60}")
            print(f"PRD: {result.prd_name}")
            print(f"Status: {result.status.upper()}")
            print(f"Reason: {result.reason}")
            print(f"Time: {result.rolled_back_at[:19]}")
            print()

            print(f"Commits:")
            print(f"  Tracked: {result.commits_tracked}")
            print(f"  Reverted: {result.commits_reverted}")
            if result.commits_failed:
                print(f"  Failed: {len(result.commits_failed)}")
                for sha in result.commits_failed:
                    print(f"    - {sha}")

            if result.revert_commits:
                print(f"\nRevert commits created:")
                for sha in result.revert_commits:
                    print(f"  - {sha[:8]}")

            if result.validation.ran:
                print(f"\nValidation:")
                status = "PASS" if result.validation.passed else "FAIL"
                print(f"  Status: {status}")
                if result.validation.error:
                    print(f"  Error: {result.validation.error}")

            if result.capabilities_reverted:
                print(f"\nCapabilities reverted:")
                for cap in result.capabilities_reverted:
                    print(f"  - {cap}")

            if result.warnings:
                print(f"\nWarnings:")
                for warning in result.warnings:
                    print(f"  - {warning}")

            if result.error_message:
                print(f"\nError: {result.error_message}")

            print()

        # Exit with appropriate code
        sys.exit(0 if result.status in [RollbackStatus.SUCCESS.value, RollbackStatus.SKIPPED.value] else 1)

    elif args.command == "status":
        status = rollback_mgr.get_tracking_status(args.prd_name)

        if not status:
            print(f"No tracking data found for: {args.prd_name}")
            sys.exit(1)

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"IMPROVEMENT TRACKING STATUS")
            print(f"{'='*60}")
            print(f"PRD Name: {status['prd_name']}")
            print(f"Branch: {status['branch_name']}")
            print(f"Status: {status['status']}")
            print(f"Base Commit: {status['base_commit'][:8] if status['base_commit'] else 'N/A'}")
            print(f"Commits Tracked: {len(status['commits'])}")
            print(f"Started: {status['started_at'][:19] if status['started_at'] else 'N/A'}")
            if status['completed_at']:
                print(f"Completed: {status['completed_at'][:19]}")
            print()

    elif args.command == "commits":
        commits = rollback_mgr.get_tracked_commits(args.prd_name)

        if not commits:
            print(f"No commits tracked for: {args.prd_name}")
            sys.exit(0)

        if args.json:
            print(json.dumps([c.to_dict() for c in commits], indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"TRACKED COMMITS FOR: {args.prd_name}")
            print(f"{'='*60}")
            print(f"{'SHA':<10} {'Date':<20} {'Author':<20} Message")
            print("-" * 70)
            for commit in commits:
                print(f"{commit.sha[:8]:<10} {commit.date[:19]:<20} {commit.author[:19]:<20} {commit.message[:40]}")
            print()

    elif args.command == "track":
        success = rollback_mgr.track_commit(args.prd_name, args.commit_sha)

        if success:
            print(f"Tracked commit {args.commit_sha[:8]} for {args.prd_name}")
        else:
            print(f"Failed to track commit")
            sys.exit(1)

    elif args.command == "start-tracking":
        branch = args.branch or rollback_mgr._get_current_branch()
        success = rollback_mgr.track_improvement_start(args.prd_name, branch)

        if success:
            print(f"Started tracking for {args.prd_name} on branch {branch}")
        else:
            print(f"Failed to start tracking")
            sys.exit(1)

    elif args.command == "complete-tracking":
        success = rollback_mgr.track_improvement_complete(args.prd_name)

        if success:
            print(f"Marked {args.prd_name} as complete")
        else:
            print(f"Failed to mark complete (not found or error)")
            sys.exit(1)

    elif args.command == "history":
        history = rollback_mgr.get_rollback_history(limit=args.limit)

        if not history:
            print("No rollback history found.")
            sys.exit(0)

        if args.json:
            print(json.dumps([e.to_dict() for e in history], indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"ROLLBACK HISTORY (last {args.limit})")
            print(f"{'='*60}")
            print(f"{'PRD Name':<35} {'Status':<10} {'Reverted':<8} {'Date':<20}")
            print("-" * 75)
            for entry in history:
                print(
                    f"{entry.prd_name[:34]:<35} "
                    f"{entry.status:<10} "
                    f"{entry.commits_reverted:<8} "
                    f"{entry.rolled_back_at[:19]:<20}"
                )
            print()

    elif args.command == "list":
        tracked = rollback_mgr.list_all_tracked()

        if not tracked:
            print("No improvements being tracked.")
            sys.exit(0)

        if args.json:
            print(json.dumps(tracked, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"TRACKED IMPROVEMENTS")
            print(f"{'='*60}")
            print(f"{'PRD Name':<35} {'Status':<15} {'Commits':<8} Branch")
            print("-" * 75)
            for item in tracked:
                print(
                    f"{item['prd_name'][:34]:<35} "
                    f"{item['status']:<15} "
                    f"{item['commit_count']:<8} "
                    f"{item['branch_name']}"
                )
            print()


if __name__ == "__main__":
    main()
