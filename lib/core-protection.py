#!/usr/bin/env python3
"""
core-protection.py - Core File Protection System for claude-loop

Implements strict immutability rules for core files. No automated modifications
are allowed to core files - they require manual commits only.

Key Features:
- CORE_FILES list of protected files (foundational to claude-loop)
- is_core_file(path) -> bool with clear classification
- Block ALL automated modifications to core files
- No --force flag to override (core changes require manual commits)
- Audit logging of all core access attempts
- CLI for managing protected files

Principles:
- L0 core must be immutable. No automated changes, period.
- Improvement proposals affecting core -> auto-rejected with explanation
- All access attempts logged for security audit

Usage:
    # List protected files
    python lib/core-protection.py list

    # Show access audit log
    python lib/core-protection.py audit

    # Add a file to protection (requires confirmation)
    python lib/core-protection.py add <path> --confirm

    # Remove a file from protection (requires confirmation)
    python lib/core-protection.py remove <path> --confirm

    # Check if a file is protected
    python lib/core-protection.py check <path>

    # Validate a set of file changes (for pre-commit/CI)
    python lib/core-protection.py validate-changes <file1> <file2> ...
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

# Default core files that are always protected
# These are foundational files that should never be modified by automation
DEFAULT_CORE_FILES = [
    # Main orchestration
    "claude-loop.sh",

    # Core libraries (foundation)
    "lib/execution-logger.sh",
    "lib/core-protection.py",  # Self-protection
    "lib/prd-parser.sh",
    "lib/monitoring.sh",
    "lib/worker.sh",
    "lib/parallel.sh",
    "lib/merge-controller.py",

    # Core configuration
    "prompt.md",
    "AGENTS.md",

    # Security-sensitive files
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "**/secrets/**",
    "**/credentials*",
]

# Files that can never be unprotected (absolute core)
IMMUTABLE_CORE = [
    "claude-loop.sh",
    "lib/core-protection.py",
    "lib/execution-logger.sh",
]

# Configuration and audit files
CONFIG_FILE = ".claude-loop/core_protection_config.json"
AUDIT_LOG_FILE = ".claude-loop/core_access_audit.log"
BASE_DIR = Path.cwd()


# ============================================================================
# Enums
# ============================================================================

class AccessType(str, Enum):
    """Types of access attempts to core files."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MODIFY = "modify"
    PROPOSAL = "proposal"  # Improvement proposal affecting core

    def __str__(self) -> str:
        return self.value


class BlockReason(str, Enum):
    """Reasons for blocking access to core files."""
    CORE_FILE = "core_file"           # File is in core protection list
    IMMUTABLE = "immutable"           # File is in immutable core (can't be unprotected)
    PATTERN_MATCH = "pattern_match"   # File matches a protected pattern
    SECURITY = "security"             # File contains sensitive data

    def __str__(self) -> str:
        return self.value


class ActionResult(str, Enum):
    """Result of an access attempt."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    AUDIT_ONLY = "audit_only"  # Read access logged but allowed

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CoreFileEntry:
    """An entry in the core files protection list.

    Attributes:
        path: File path (can include wildcards)
        added_at: When the file was added to protection
        added_by: Who added it (manual/default)
        reason: Why this file is protected
        is_pattern: Whether path contains wildcards
        is_immutable: Whether this can be removed from protection
    """
    path: str
    added_at: str = ""
    added_by: str = "default"
    reason: str = ""
    is_pattern: bool = False
    is_immutable: bool = False

    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.is_pattern:
            self.is_pattern = "*" in self.path or "?" in self.path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoreFileEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AccessAttempt:
    """Record of an access attempt to a core file.

    Attributes:
        path: File that was accessed
        access_type: Type of access (read/write/delete/modify/proposal)
        timestamp: When the attempt occurred
        result: Whether it was allowed/blocked
        block_reason: Why it was blocked (if blocked)
        caller: What requested the access (agent/script/etc.)
        context: Additional context about the access
        proposal_id: If this was from an improvement proposal
    """
    path: str
    access_type: str
    timestamp: str = ""
    result: str = ActionResult.BLOCKED.value
    block_reason: str = ""
    caller: str = ""
    context: str = ""
    proposal_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessAttempt":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_log_line(self) -> str:
        """Format as a log line for the audit log."""
        return json.dumps(self.to_dict())


@dataclass
class ProtectionConfig:
    """Configuration for core file protection.

    Attributes:
        core_files: List of protected files
        custom_additions: Files added by user
        custom_removals: Default files removed by user
        last_updated: When config was last modified
    """
    core_files: list[CoreFileEntry] = field(default_factory=list)
    custom_additions: list[str] = field(default_factory=list)
    custom_removals: list[str] = field(default_factory=list)
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_files": [f.to_dict() for f in self.core_files],
            "custom_additions": self.custom_additions,
            "custom_removals": self.custom_removals,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProtectionConfig":
        core_files = [
            CoreFileEntry.from_dict(f) if isinstance(f, dict) else f
            for f in data.get("core_files", [])
        ]
        return cls(
            core_files=core_files,
            custom_additions=data.get("custom_additions", []),
            custom_removals=data.get("custom_removals", []),
            last_updated=data.get("last_updated", ""),
        )


@dataclass
class CheckResult:
    """Result of checking if a file is protected.

    Attributes:
        path: The file path that was checked
        is_protected: Whether the file is protected
        is_immutable: Whether the file is in immutable core
        block_reason: Why it's protected (if protected)
        matched_pattern: Which pattern matched (if pattern match)
        entry: The matching CoreFileEntry (if found)
    """
    path: str
    is_protected: bool
    is_immutable: bool = False
    block_reason: str = ""
    matched_pattern: str = ""
    entry: CoreFileEntry | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "path": self.path,
            "is_protected": self.is_protected,
            "is_immutable": self.is_immutable,
            "block_reason": self.block_reason,
            "matched_pattern": self.matched_pattern,
        }
        if self.entry:
            result["entry"] = self.entry.to_dict()
        return result


@dataclass
class ValidationResult:
    """Result of validating a set of file changes.

    Attributes:
        valid: Whether all changes are allowed
        blocked_files: List of files that would be blocked
        allowed_files: List of files that are allowed
        warnings: Any warnings (e.g., near-core files)
    """
    valid: bool
    blocked_files: list[CheckResult] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "blocked_files": [f.to_dict() for f in self.blocked_files],
            "allowed_files": self.allowed_files,
            "warnings": self.warnings,
        }


# ============================================================================
# Core Protection Manager
# ============================================================================

class CoreProtectionManager:
    """Manages core file protection for claude-loop.

    Enforces strict immutability rules for core files.
    No --force flag exists - core changes require manual commits.
    """

    def __init__(
        self,
        base_dir: str | Path = ".",
        verbose: bool = False,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.config_file = self.base_dir / CONFIG_FILE
        self.audit_log_file = self.base_dir / AUDIT_LOG_FILE
        self.verbose = verbose

        # Runtime state
        self._config: ProtectionConfig | None = None
        self._protected_paths: set[str] = set()
        self._protected_patterns: list[str] = []

    def _log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[core-protection] {message}", file=sys.stderr)

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Configuration Management
    # -------------------------------------------------------------------------

    def _load_config(self) -> ProtectionConfig:
        """Load protection configuration."""
        if self._config is not None:
            return self._config

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                self._config = ProtectionConfig.from_dict(data)
            except Exception as e:
                self._log(f"Error loading config: {e}")
                self._config = self._create_default_config()
        else:
            self._config = self._create_default_config()

        # Build lookup structures
        self._build_lookup_structures()

        return self._config

    def _create_default_config(self) -> ProtectionConfig:
        """Create default configuration with core files."""
        entries = []
        for path in DEFAULT_CORE_FILES:
            is_immutable = path in IMMUTABLE_CORE
            entry = CoreFileEntry(
                path=path,
                added_by="default",
                reason="Foundational claude-loop file" if is_immutable else "Core infrastructure",
                is_immutable=is_immutable,
            )
            entries.append(entry)

        return ProtectionConfig(
            core_files=entries,
            last_updated=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def _save_config(self) -> None:
        """Save protection configuration."""
        self._ensure_dirs()
        config = self._load_config()
        config.last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            with open(self.config_file, "w") as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception as e:
            self._log(f"Error saving config: {e}")

    def _build_lookup_structures(self) -> None:
        """Build fast lookup structures for protection checking."""
        config = self._config
        if config is None:
            return

        self._protected_paths = set()
        self._protected_patterns = []

        for entry in config.core_files:
            if entry.is_pattern:
                self._protected_patterns.append(entry.path)
            else:
                self._protected_paths.add(entry.path)

    # -------------------------------------------------------------------------
    # Core Protection Logic
    # -------------------------------------------------------------------------

    def is_core_file(self, path: str | Path) -> bool:
        """Check if a file is a protected core file.

        Args:
            path: File path to check (relative or absolute)

        Returns:
            True if the file is protected, False otherwise
        """
        result = self.check_file(path)
        return result.is_protected

    def check_file(self, path: str | Path) -> CheckResult:
        """Check protection status of a file with detailed info.

        Args:
            path: File path to check

        Returns:
            CheckResult with detailed protection information
        """
        config = self._load_config()

        # Normalize path
        path_str = str(path)
        if Path(path).is_absolute():
            try:
                path_str = str(Path(path).relative_to(self.base_dir))
            except ValueError:
                # Path is outside base_dir
                pass

        # Normalize separators
        path_str = path_str.replace("\\", "/")

        # Check exact match first
        if path_str in self._protected_paths:
            entry = next(
                (e for e in config.core_files if e.path == path_str),
                None
            )
            is_immutable = path_str in IMMUTABLE_CORE
            return CheckResult(
                path=path_str,
                is_protected=True,
                is_immutable=is_immutable,
                block_reason=BlockReason.IMMUTABLE.value if is_immutable else BlockReason.CORE_FILE.value,
                matched_pattern=path_str,
                entry=entry,
            )

        # Check patterns
        for pattern in self._protected_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                entry = next(
                    (e for e in config.core_files if e.path == pattern),
                    None
                )
                is_security = any(
                    s in pattern.lower()
                    for s in ["secret", "credential", ".pem", ".key", ".env"]
                )
                return CheckResult(
                    path=path_str,
                    is_protected=True,
                    is_immutable=False,
                    block_reason=BlockReason.SECURITY.value if is_security else BlockReason.PATTERN_MATCH.value,
                    matched_pattern=pattern,
                    entry=entry,
                )

        return CheckResult(
            path=path_str,
            is_protected=False,
            is_immutable=False,
        )

    def validate_changes(self, paths: list[str | Path]) -> ValidationResult:
        """Validate a set of file changes.

        Args:
            paths: List of files that would be modified

        Returns:
            ValidationResult indicating if changes are allowed
        """
        blocked = []
        allowed = []
        warnings = []

        for path in paths:
            result = self.check_file(path)
            if result.is_protected:
                blocked.append(result)
            else:
                allowed.append(str(path))

        return ValidationResult(
            valid=len(blocked) == 0,
            blocked_files=blocked,
            allowed_files=allowed,
            warnings=warnings,
        )

    def block_modification(
        self,
        path: str | Path,
        access_type: str = AccessType.MODIFY.value,
        caller: str = "",
        context: str = "",
        proposal_id: str = "",
    ) -> tuple[bool, str]:
        """Attempt to modify a file and block if protected.

        This is the main entry point for checking modifications.
        It logs the attempt and returns whether the modification is blocked.

        Args:
            path: File to modify
            access_type: Type of access (write/delete/modify)
            caller: What is requesting the modification
            context: Additional context
            proposal_id: If from an improvement proposal

        Returns:
            Tuple of (blocked: bool, reason: str)
        """
        result = self.check_file(path)

        # Log the access attempt
        attempt = AccessAttempt(
            path=str(path),
            access_type=access_type,
            result=ActionResult.BLOCKED.value if result.is_protected else ActionResult.ALLOWED.value,
            block_reason=result.block_reason,
            caller=caller,
            context=context,
            proposal_id=proposal_id,
        )
        self._log_access(attempt)

        if result.is_protected:
            reason = self._format_block_reason(result)
            return True, reason

        return False, ""

    def _format_block_reason(self, result: CheckResult) -> str:
        """Format a human-readable block reason."""
        if result.is_immutable:
            return (
                f"BLOCKED: '{result.path}' is an IMMUTABLE core file. "
                "Core files cannot be modified by automation. "
                "Manual commit required. See CONTRIBUTING.md for the process."
            )
        elif result.block_reason == BlockReason.SECURITY.value:
            return (
                f"BLOCKED: '{result.path}' matches security-sensitive pattern '{result.matched_pattern}'. "
                "Security files cannot be modified by automation."
            )
        elif result.block_reason == BlockReason.PATTERN_MATCH.value:
            return (
                f"BLOCKED: '{result.path}' matches protected pattern '{result.matched_pattern}'. "
                "Protected files require manual modification."
            )
        else:
            return (
                f"BLOCKED: '{result.path}' is a protected core file. "
                "Core changes require manual commits. See CONTRIBUTING.md."
            )

    # -------------------------------------------------------------------------
    # Improvement Proposal Integration
    # -------------------------------------------------------------------------

    def check_proposal_affects_core(
        self,
        file_scope: list[str],
        proposal_id: str = "",
    ) -> tuple[bool, list[str], str]:
        """Check if an improvement proposal affects core files.

        Args:
            file_scope: List of files the proposal would modify
            proposal_id: ID of the proposal (for audit logging)

        Returns:
            Tuple of (affects_core: bool, affected_files: list, rejection_reason: str)
        """
        affected = []

        for path in file_scope:
            result = self.check_file(path)
            if result.is_protected:
                affected.append(path)
                # Log the proposal attempt
                self._log_access(AccessAttempt(
                    path=str(path),
                    access_type=AccessType.PROPOSAL.value,
                    result=ActionResult.BLOCKED.value,
                    block_reason=result.block_reason,
                    caller="improvement_proposal",
                    proposal_id=proposal_id,
                ))

        if affected:
            rejection_reason = (
                f"PROPOSAL AUTO-REJECTED: Affects {len(affected)} core file(s): "
                f"{', '.join(affected[:5])}{'...' if len(affected) > 5 else ''}. "
                "Improvement proposals cannot modify core files. "
                "Core changes require manual implementation. See CONTRIBUTING.md."
            )
            return True, affected, rejection_reason

        return False, [], ""

    # -------------------------------------------------------------------------
    # Audit Logging
    # -------------------------------------------------------------------------

    def _log_access(self, attempt: AccessAttempt) -> None:
        """Log an access attempt to the audit log."""
        self._ensure_dirs()
        try:
            with open(self.audit_log_file, "a") as f:
                f.write(attempt.to_log_line() + "\n")
        except Exception as e:
            self._log(f"Error writing audit log: {e}")

    def get_audit_log(
        self,
        limit: int = 100,
        access_type: str | None = None,
        result: str | None = None,
        path_filter: str | None = None,
    ) -> list[AccessAttempt]:
        """Read the audit log with optional filters.

        Args:
            limit: Maximum number of entries to return
            access_type: Filter by access type
            result: Filter by result (allowed/blocked)
            path_filter: Filter by path pattern

        Returns:
            List of AccessAttempt records
        """
        if not self.audit_log_file.exists():
            return []

        attempts = []
        try:
            with open(self.audit_log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        attempt = AccessAttempt.from_dict(data)

                        # Apply filters
                        if access_type and attempt.access_type != access_type:
                            continue
                        if result and attempt.result != result:
                            continue
                        if path_filter and not fnmatch.fnmatch(attempt.path, path_filter):
                            continue

                        attempts.append(attempt)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self._log(f"Error reading audit log: {e}")

        # Return most recent first, limited
        return list(reversed(attempts[-limit:]))

    def get_audit_stats(self) -> dict[str, Any]:
        """Get statistics from the audit log."""
        attempts = self.get_audit_log(limit=10000)  # Get all

        stats = {
            "total_attempts": len(attempts),
            "blocked": sum(1 for a in attempts if a.result == ActionResult.BLOCKED.value),
            "allowed": sum(1 for a in attempts if a.result == ActionResult.ALLOWED.value),
            "by_access_type": {},
            "by_block_reason": {},
            "most_accessed": {},
        }

        for attempt in attempts:
            # By access type
            stats["by_access_type"][attempt.access_type] = \
                stats["by_access_type"].get(attempt.access_type, 0) + 1

            # By block reason
            if attempt.block_reason:
                stats["by_block_reason"][attempt.block_reason] = \
                    stats["by_block_reason"].get(attempt.block_reason, 0) + 1

            # Most accessed files
            stats["most_accessed"][attempt.path] = \
                stats["most_accessed"].get(attempt.path, 0) + 1

        # Sort most accessed
        stats["most_accessed"] = dict(
            sorted(stats["most_accessed"].items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return stats

    # -------------------------------------------------------------------------
    # Protection List Management
    # -------------------------------------------------------------------------

    def list_protected_files(self) -> list[CoreFileEntry]:
        """List all protected files."""
        config = self._load_config()
        return config.core_files

    def add_protected_file(
        self,
        path: str,
        reason: str = "",
        confirm: bool = False,
    ) -> tuple[bool, str]:
        """Add a file to the protection list.

        Args:
            path: File path to protect
            reason: Why this file should be protected
            confirm: Must be True to actually add

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not confirm:
            return False, (
                "Adding files to core protection requires --confirm flag. "
                "This action protects the file from ALL automated modifications."
            )

        config = self._load_config()

        # Check if already protected
        existing = next((e for e in config.core_files if e.path == path), None)
        if existing:
            return False, f"File '{path}' is already protected"

        # Add new entry
        entry = CoreFileEntry(
            path=path,
            added_by="manual",
            reason=reason or "User-added protection",
            is_immutable=False,
        )
        config.core_files.append(entry)
        config.custom_additions.append(path)

        self._save_config()
        self._build_lookup_structures()

        return True, f"Added '{path}' to core protection"

    def remove_protected_file(
        self,
        path: str,
        confirm: bool = False,
    ) -> tuple[bool, str]:
        """Remove a file from the protection list.

        Args:
            path: File path to unprotect
            confirm: Must be True to actually remove

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not confirm:
            return False, (
                "Removing files from core protection requires --confirm flag. "
                "This action allows automated modifications to the file."
            )

        # Check if immutable
        if path in IMMUTABLE_CORE:
            return False, (
                f"CANNOT REMOVE: '{path}' is an IMMUTABLE core file. "
                "Immutable files can never be removed from protection."
            )

        config = self._load_config()

        # Find and check entry
        entry = next((e for e in config.core_files if e.path == path), None)
        if entry is None:
            return False, f"File '{path}' is not in protection list"

        if entry.is_immutable:
            return False, (
                f"CANNOT REMOVE: '{path}' is marked as immutable. "
                "This file cannot be removed from protection."
            )

        # Remove entry
        config.core_files = [e for e in config.core_files if e.path != path]
        if path in config.custom_additions:
            config.custom_additions.remove(path)
        else:
            config.custom_removals.append(path)

        self._save_config()
        self._build_lookup_structures()

        return True, f"Removed '{path}' from core protection"


# ============================================================================
# CLI Interface
# ============================================================================

def format_file_table(entries: list[CoreFileEntry]) -> str:
    """Format protected files as a table."""
    if not entries:
        return "No protected files found."

    lines = []
    lines.append(f"{'Path':<45} {'Type':<12} {'Immutable':<10} {'Added By':<10}")
    lines.append("-" * 80)

    for entry in entries:
        file_type = "pattern" if entry.is_pattern else "file"
        immutable = "YES" if entry.is_immutable else "no"
        lines.append(
            f"{entry.path:<45} {file_type:<12} {immutable:<10} {entry.added_by:<10}"
        )

    return "\n".join(lines)


def format_audit_table(attempts: list[AccessAttempt]) -> str:
    """Format audit log as a table."""
    if not attempts:
        return "No audit entries found."

    lines = []
    lines.append(f"{'Timestamp':<24} {'Path':<30} {'Type':<10} {'Result':<10} {'Reason':<15}")
    lines.append("-" * 95)

    for attempt in attempts:
        # Truncate path if too long
        path = attempt.path[:28] + ".." if len(attempt.path) > 30 else attempt.path
        # Format timestamp
        ts = attempt.timestamp[:19] if attempt.timestamp else "N/A"
        lines.append(
            f"{ts:<24} {path:<30} {attempt.access_type:<10} "
            f"{attempt.result:<10} {attempt.block_reason[:15]:<15}"
        )

    return "\n".join(lines)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Core File Protection System for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all protected files
  python lib/core-protection.py list

  # Check if a specific file is protected
  python lib/core-protection.py check lib/worker.sh

  # View audit log
  python lib/core-protection.py audit

  # Add a file to protection
  python lib/core-protection.py add my-config.yaml --reason "Critical config" --confirm

  # Remove a file from protection
  python lib/core-protection.py remove my-config.yaml --confirm

  # Validate a set of changes (for CI/pre-commit)
  python lib/core-protection.py validate-changes file1.py file2.sh
        """
    )

    # Global options
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Base directory (default: current directory)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List protected files")
    list_parser.add_argument("--patterns-only", action="store_true", help="Show only patterns")
    list_parser.add_argument("--files-only", action="store_true", help="Show only explicit files")
    list_parser.add_argument("--immutable-only", action="store_true", help="Show only immutable files")

    # check command
    check_parser = subparsers.add_parser("check", help="Check if a file is protected")
    check_parser.add_argument("path", help="File path to check")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Show access audit log")
    audit_parser.add_argument("--limit", type=int, default=50, help="Number of entries")
    audit_parser.add_argument("--type", dest="access_type", help="Filter by access type")
    audit_parser.add_argument("--blocked-only", action="store_true", help="Show only blocked")
    audit_parser.add_argument("--stats", action="store_true", help="Show statistics instead")

    # add command
    add_parser = subparsers.add_parser("add", help="Add file to protection")
    add_parser.add_argument("path", help="File path to protect")
    add_parser.add_argument("--reason", default="", help="Why this file should be protected")
    add_parser.add_argument("--confirm", action="store_true", help="Confirm the action")

    # remove command
    remove_parser = subparsers.add_parser("remove", help="Remove file from protection")
    remove_parser.add_argument("path", help="File path to unprotect")
    remove_parser.add_argument("--confirm", action="store_true", help="Confirm the action")

    # validate-changes command
    validate_parser = subparsers.add_parser("validate-changes", help="Validate file changes")
    validate_parser.add_argument("paths", nargs="+", help="Files to validate")

    # check-proposal command
    proposal_parser = subparsers.add_parser(
        "check-proposal",
        help="Check if improvement proposal affects core"
    )
    proposal_parser.add_argument("--file-scope", nargs="+", required=True, help="Files in scope")
    proposal_parser.add_argument("--proposal-id", default="", help="Proposal ID for logging")

    args = parser.parse_args()

    manager = CoreProtectionManager(
        base_dir=args.base_dir,
        verbose=args.verbose,
    )

    if args.command == "list":
        entries = manager.list_protected_files()

        # Apply filters
        if args.patterns_only:
            entries = [e for e in entries if e.is_pattern]
        if args.files_only:
            entries = [e for e in entries if not e.is_pattern]
        if args.immutable_only:
            entries = [e for e in entries if e.is_immutable]

        if args.json:
            print(json.dumps([e.to_dict() for e in entries], indent=2))
        else:
            print(format_file_table(entries))
            print(f"\nTotal: {len(entries)} protected entries")
            immutable_count = sum(1 for e in entries if e.is_immutable)
            print(f"Immutable (cannot be removed): {immutable_count}")
        return 0

    elif args.command == "check":
        result = manager.check_file(args.path)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.is_protected:
                status = "IMMUTABLE CORE FILE" if result.is_immutable else "PROTECTED"
                print(f"{status}: {result.path}")
                print(f"Reason: {result.block_reason}")
                if result.matched_pattern:
                    print(f"Matched pattern: {result.matched_pattern}")
                if result.entry and result.entry.reason:
                    print(f"Description: {result.entry.reason}")
            else:
                print(f"NOT PROTECTED: {result.path}")
        return 0 if not result.is_protected else 1

    elif args.command == "audit":
        if args.stats:
            stats = manager.get_audit_stats()
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("Core Access Audit Statistics")
                print("=" * 40)
                print(f"Total attempts: {stats['total_attempts']}")
                print(f"Blocked: {stats['blocked']}")
                print(f"Allowed: {stats['allowed']}")
                print()
                print("By Access Type:")
                for k, v in stats["by_access_type"].items():
                    print(f"  {k}: {v}")
                print()
                print("By Block Reason:")
                for k, v in stats["by_block_reason"].items():
                    print(f"  {k}: {v}")
                print()
                print("Most Accessed Files:")
                for k, v in list(stats["most_accessed"].items())[:5]:
                    print(f"  {k}: {v}")
            return 0

        result_filter = ActionResult.BLOCKED.value if args.blocked_only else None
        attempts = manager.get_audit_log(
            limit=args.limit,
            access_type=args.access_type,
            result=result_filter,
        )

        if args.json:
            print(json.dumps([a.to_dict() for a in attempts], indent=2))
        else:
            print(format_audit_table(attempts))
            print(f"\nShowing {len(attempts)} most recent entries")
        return 0

    elif args.command == "add":
        success, message = manager.add_protected_file(
            args.path,
            reason=args.reason,
            confirm=args.confirm,
        )
        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)
        return 0 if success else 1

    elif args.command == "remove":
        success, message = manager.remove_protected_file(
            args.path,
            confirm=args.confirm,
        )
        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)
        return 0 if success else 1

    elif args.command == "validate-changes":
        result = manager.validate_changes(args.paths)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.valid:
                print("VALID: All changes are allowed")
                print(f"Files to modify: {len(result.allowed_files)}")
            else:
                print("BLOCKED: Some changes affect core files")
                print()
                for blocked in result.blocked_files:
                    print(f"  BLOCKED: {blocked.path}")
                    print(f"    Reason: {blocked.block_reason}")
                    if blocked.matched_pattern:
                        print(f"    Pattern: {blocked.matched_pattern}")
                print()
                print(f"Blocked files: {len(result.blocked_files)}")
                print(f"Allowed files: {len(result.allowed_files)}")
        return 0 if result.valid else 1

    elif args.command == "check-proposal":
        affects_core, affected_files, reason = manager.check_proposal_affects_core(
            args.file_scope,
            proposal_id=args.proposal_id,
        )
        if args.json:
            print(json.dumps({
                "affects_core": affects_core,
                "affected_files": affected_files,
                "rejection_reason": reason,
            }, indent=2))
        else:
            if affects_core:
                print("PROPOSAL REJECTED: Affects core files")
                print()
                print(reason)
                print()
                print("Affected files:")
                for f in affected_files:
                    print(f"  - {f}")
            else:
                print("PROPOSAL ALLOWED: No core files affected")
        return 1 if affects_core else 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
