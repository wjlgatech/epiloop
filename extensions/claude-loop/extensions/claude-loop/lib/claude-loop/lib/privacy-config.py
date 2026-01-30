#!/usr/bin/env python3
# pylint: disable=broad-except
"""
privacy-config.py - Privacy-First Local-Only Architecture for claude-loop

Provides privacy configuration and data management for enterprise users who
require all data to stay local with no external communication by default.

Features:
- Default FULLY_LOCAL mode: no network calls for improvement system
- All experience data stored locally in .claude-loop/
- No telemetry, no analytics, no phone-home by default
- Optional TEAM_SYNC mode: sync via shared folder or git (no cloud)
- Optional FEDERATED mode: requires explicit enterprise agreement
- Privacy audit: CLI command to show all data that would be shared
- Data export: portable format for migration
- Data delete: complete removal with confirmation

Usage:
    # Show current privacy status and data locations
    python3 lib/privacy-config.py status

    # Run privacy audit (list all stored data)
    python3 lib/privacy-config.py audit

    # Export audit report to file
    python3 lib/privacy-config.py audit --export audit_report.json

    # Export all experiences in portable format
    python3 lib/privacy-config.py export --output experiences_backup.jsonl.gz

    # Export experiences for a specific domain
    python3 lib/privacy-config.py export --domain unity_xr --output unity_backup.jsonl.gz

    # Purge all data (requires confirmation)
    python3 lib/privacy-config.py purge --confirm

    # Set privacy mode
    python3 lib/privacy-config.py set-mode fully_local
    python3 lib/privacy-config.py set-mode team_sync --sync-path /shared/team/claude-loop
    python3 lib/privacy-config.py set-mode federated --agreement-id AGR-12345

CLI Options:
    --json              Output as JSON
    --verbose           Enable verbose output
"""

import argparse
import gzip
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# Constants
# ============================================================================

CLAUDE_LOOP_DIR = ".claude-loop"
CONFIG_FILE = ".claude-loop/privacy_config.json"
DEFAULT_MODE = "FULLY_LOCAL"

# Data locations that store user data
DATA_LOCATIONS = {
    "experiences": ".claude-loop/experiences/",
    "retrieval_outcomes": ".claude-loop/retrieval_outcomes.jsonl",
    "execution_log": ".claude-loop/execution_log.jsonl",
    "improvement_queue": ".claude-loop/improvement_queue.json",
    "capability_gaps": ".claude-loop/capability_gaps.json",
    "analysis_cache": ".claude-loop/analysis_cache/",
    "improvement_history": ".claude-loop/improvement_history.jsonl",
    "improvements_prd": ".claude-loop/improvements/",
    "validation_reports": ".claude-loop/validation_reports/",
    "held_out_cases": ".claude-loop/held_out_cases/",
    "runs": ".claude-loop/runs/",
    "cache": ".claude-loop/cache/",
    "daemon_status": ".claude-loop/daemon_status.json",
    "daemon_log": ".claude-loop/daemon.log",
}

# Files that should NEVER be shared (even in team sync)
NEVER_SHARE = [
    "daemon.pid",
    "daemon.lock",
    "*.pid",
    "*.lock",
]


# ============================================================================
# Privacy Mode Enum
# ============================================================================

class PrivacyMode(str, Enum):
    """Privacy modes for claude-loop data handling."""

    FULLY_LOCAL = "fully_local"
    """Default mode. All data stays local. No network calls for improvement system.
    No telemetry, no analytics, no phone-home. Complete isolation."""

    TEAM_SYNC = "team_sync"
    """Team synchronization via shared folder or git repository.
    NO cloud services involved - only local filesystem or git.
    Experiences shared with team members via manual export/import."""

    FEDERATED = "federated"
    """Federated mode for enterprise deployments.
    Requires explicit enterprise agreement and configuration.
    May enable limited telemetry with consent. Not recommended for sensitive projects."""


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PrivacyConfig:
    """Privacy configuration for claude-loop."""
    mode: PrivacyMode
    sync_path: Optional[str] = None  # For TEAM_SYNC mode
    git_remote: Optional[str] = None  # For git-based TEAM_SYNC
    agreement_id: Optional[str] = None  # For FEDERATED mode
    telemetry_enabled: bool = False  # Always False unless FEDERATED with consent
    analytics_enabled: bool = False  # Always False unless FEDERATED with consent
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        data = asdict(self)
        data['mode'] = self.mode.value if isinstance(self.mode, PrivacyMode) else self.mode
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'PrivacyConfig':
        mode_value = data.get('mode', DEFAULT_MODE)
        if isinstance(mode_value, str):
            try:
                data['mode'] = PrivacyMode(mode_value.lower())
            except ValueError:
                data['mode'] = PrivacyMode.FULLY_LOCAL
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def default(cls) -> 'PrivacyConfig':
        """Create default privacy configuration (FULLY_LOCAL)."""
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return cls(
            mode=PrivacyMode.FULLY_LOCAL,
            telemetry_enabled=False,
            analytics_enabled=False,
            created_at=now,
            updated_at=now,
        )


@dataclass
class DataLocation:
    """Information about a data storage location."""
    name: str
    path: str
    exists: bool
    size_bytes: int
    file_count: int
    item_count: int  # Number of records/entries
    description: str
    sensitive: bool
    shareable: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    """Privacy audit report showing all stored data."""
    generated_at: str
    privacy_mode: str
    data_locations: List[DataLocation]
    total_size_bytes: int
    total_files: int
    total_items: int
    shareable_data: List[str]
    sensitive_data: List[str]
    would_share: List[str]  # What would be shared in current mode
    summary: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data['data_locations'] = [loc.to_dict() if hasattr(loc, 'to_dict') else loc
                                  for loc in self.data_locations]
        return data


@dataclass
class ExportResult:
    """Result from exporting experiences."""
    success: bool
    output_path: str
    experience_count: int
    domains_included: List[str]
    size_bytes: int
    format: str
    checksum: str
    exported_at: str
    filters_applied: Dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PurgeResult:
    """Result from purging data."""
    success: bool
    items_removed: int
    bytes_freed: int
    locations_cleared: List[str]
    purged_at: str
    backup_path: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Privacy Manager Class
# ============================================================================

class PrivacyManager:
    """
    Manages privacy configuration and data for claude-loop.

    Enforces local-only data storage by default. Provides tools for
    auditing, exporting, and purging data.
    """

    def __init__(self, base_dir: str = "."):
        """Initialize the privacy manager.

        Args:
            base_dir: Base directory for claude-loop (default: current directory)
        """
        self.base_dir = Path(base_dir)
        self.config_file = self.base_dir / CONFIG_FILE
        self.config = self._load_config()

    def _load_config(self) -> PrivacyConfig:
        """Load privacy configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return PrivacyConfig.from_dict(data)
            except (json.JSONDecodeError, IOError):
                pass
        return PrivacyConfig.default()

    def _save_config(self) -> None:
        """Save privacy configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.updated_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        with open(self.config_file, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)

    def get_status(self) -> Dict[str, Any]:
        """Get current privacy status and data locations.

        Returns:
            Dictionary with privacy mode and data location info
        """
        locations = []
        total_size = 0
        total_files = 0

        for name, rel_path in DATA_LOCATIONS.items():
            full_path = self.base_dir / rel_path
            loc_info = self._get_location_info(name, full_path)
            locations.append(loc_info)
            total_size += loc_info['size_bytes']
            total_files += loc_info['file_count']

        return {
            "mode": self.config.mode.value,
            "mode_description": self._get_mode_description(),
            "telemetry_enabled": self.config.telemetry_enabled,
            "analytics_enabled": self.config.analytics_enabled,
            "sync_path": self.config.sync_path,
            "git_remote": self.config.git_remote,
            "agreement_id": self.config.agreement_id,
            "data_locations": locations,
            "total_size_bytes": total_size,
            "total_files": total_files,
            "config_version": self.config.version,
            "created_at": self.config.created_at,
            "updated_at": self.config.updated_at,
        }

    def _get_mode_description(self) -> str:
        """Get human-readable description of current mode."""
        descriptions = {
            PrivacyMode.FULLY_LOCAL: (
                "All data stays local on this machine. No network calls for "
                "improvement system. No telemetry, no analytics, no phone-home."
            ),
            PrivacyMode.TEAM_SYNC: (
                "Team synchronization enabled via shared folder or git. "
                "No cloud services. Data shared only with configured team path."
            ),
            PrivacyMode.FEDERATED: (
                "Federated mode for enterprise. Requires explicit agreement. "
                "Limited telemetry may be enabled with consent."
            ),
        }
        return descriptions.get(self.config.mode, "Unknown mode")

    def _get_location_info(self, name: str, path: Path) -> Dict[str, Any]:
        """Get information about a data location."""
        exists = path.exists()
        size_bytes = 0
        file_count = 0
        item_count = 0

        if exists:
            if path.is_file():
                size_bytes = path.stat().st_size
                file_count = 1
                item_count = self._count_items(path)
            elif path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        size_bytes += file_path.stat().st_size
                        file_count += 1
                        item_count += self._count_items(file_path)

        # Determine sensitivity and shareability
        sensitive = name in ["execution_log", "daemon_log", "analysis_cache"]
        shareable = name in ["experiences", "improvement_queue", "capability_gaps"]

        return {
            "name": name,
            "path": str(path),
            "exists": exists,
            "size_bytes": size_bytes,
            "file_count": file_count,
            "item_count": item_count,
            "description": self._get_location_description(name),
            "sensitive": sensitive,
            "shareable": shareable,
        }

    def _get_location_description(self, name: str) -> str:
        """Get description for a data location."""
        descriptions = {
            "experiences": "Stored problem-solution experiences with domain context",
            "retrieval_outcomes": "Log of experience retrieval outcomes for quality tracking",
            "execution_log": "Detailed execution log with story outcomes",
            "improvement_queue": "Queued improvement proposals",
            "capability_gaps": "Identified capability gaps from failure analysis",
            "analysis_cache": "Cached root cause analyses",
            "improvement_history": "History of improvement approvals/rejections",
            "improvements_prd": "Generated improvement PRD files",
            "validation_reports": "Validation reports for improvements",
            "held_out_cases": "Held-out test cases for validation",
            "runs": "Per-run metrics, reports, and summaries",
            "cache": "File content cache for token optimization",
            "daemon_status": "Gap analysis daemon status",
            "daemon_log": "Gap analysis daemon activity log",
        }
        return descriptions.get(name, "Data storage")

    def _count_items(self, path: Path) -> int:
        """Count items/records in a file."""
        if not path.exists() or not path.is_file():
            return 0

        suffix = path.suffix.lower()
        try:
            if suffix == ".jsonl":
                # Count lines in JSONL file
                with open(path, 'r') as f:
                    return sum(1 for line in f if line.strip())
            elif suffix == ".json":
                # Count items in JSON array or keys in object
                with open(path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return len(data)
                    elif isinstance(data, dict):
                        # For nested structures, count top-level items
                        return len(data)
            return 1
        except Exception:
            return 0

    def audit(self) -> AuditReport:
        """Run privacy audit to show all stored data.

        Returns:
            AuditReport with detailed information about all data
        """
        locations = []
        shareable = []
        sensitive = []
        would_share = []

        for name, rel_path in DATA_LOCATIONS.items():
            full_path = self.base_dir / rel_path
            info = self._get_location_info(name, full_path)
            location = DataLocation(
                name=info['name'],
                path=info['path'],
                exists=info['exists'],
                size_bytes=info['size_bytes'],
                file_count=info['file_count'],
                item_count=info['item_count'],
                description=info['description'],
                sensitive=info['sensitive'],
                shareable=info['shareable'],
            )
            locations.append(location)

            if info['exists'] and info['size_bytes'] > 0:
                if info['shareable']:
                    shareable.append(name)
                if info['sensitive']:
                    sensitive.append(name)

        # Determine what would be shared based on mode
        if self.config.mode == PrivacyMode.FULLY_LOCAL:
            would_share = []  # Nothing shared in local mode
        elif self.config.mode == PrivacyMode.TEAM_SYNC:
            would_share = [s for s in shareable if s not in sensitive]
        elif self.config.mode == PrivacyMode.FEDERATED:
            would_share = shareable + (["analytics"] if self.config.analytics_enabled else [])

        total_size = sum(loc.size_bytes for loc in locations)
        total_files = sum(loc.file_count for loc in locations)
        total_items = sum(loc.item_count for loc in locations)

        # Generate summary
        summary = self._generate_audit_summary(
            self.config.mode, total_size, total_files, would_share
        )

        return AuditReport(
            generated_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            privacy_mode=self.config.mode.value,
            data_locations=locations,
            total_size_bytes=total_size,
            total_files=total_files,
            total_items=total_items,
            shareable_data=shareable,
            sensitive_data=sensitive,
            would_share=would_share,
            summary=summary,
        )

    def _generate_audit_summary(
        self,
        mode: PrivacyMode,
        total_size: int,
        total_files: int,
        would_share: List[str],
    ) -> str:
        """Generate human-readable audit summary."""
        size_mb = total_size / (1024 * 1024)

        if mode == PrivacyMode.FULLY_LOCAL:
            return (
                f"Privacy Mode: FULLY_LOCAL (Most Private)\n"
                f"Total Data: {size_mb:.2f} MB in {total_files} files\n"
                f"Data Shared: NONE - All data stays on this machine\n"
                f"Network Calls: NONE - No telemetry, analytics, or phone-home\n"
                f"Recommendation: Safe for enterprise and sensitive projects"
            )
        elif mode == PrivacyMode.TEAM_SYNC:
            shared_list = ", ".join(would_share) if would_share else "none"
            return (
                f"Privacy Mode: TEAM_SYNC\n"
                f"Total Data: {size_mb:.2f} MB in {total_files} files\n"
                f"Data Shared: {shared_list} (via configured sync path)\n"
                f"Network Calls: NONE - Only local filesystem or git\n"
                f"Recommendation: Safe for team collaboration"
            )
        else:  # FEDERATED
            shared_list = ", ".join(would_share) if would_share else "none"
            return (
                f"Privacy Mode: FEDERATED\n"
                f"Total Data: {size_mb:.2f} MB in {total_files} files\n"
                f"Data Shared: {shared_list}\n"
                f"Network Calls: May be enabled with consent\n"
                f"Recommendation: Review enterprise agreement before use"
            )

    def export_experiences(
        self,
        output_path: str,
        domain: Optional[str] = None,
        min_helpful_rate: float = 0.0,
        min_retrievals: int = 0,
        compress: bool = True,
    ) -> ExportResult:
        """Export experiences in portable format for migration.

        Args:
            output_path: Path for output file
            domain: Optional domain filter
            min_helpful_rate: Minimum helpful rate filter
            min_retrievals: Minimum retrieval count filter
            compress: Whether to gzip compress output

        Returns:
            ExportResult with export details
        """
        # Import ExperienceStore dynamically
        experiences_dir = self.base_dir / ".claude-loop/experiences"

        # Load experiences from JSON fallback (portable)
        fallback_file = experiences_dir / "experiences_fallback.json"
        experiences = []
        domains_seen = set()

        if fallback_file.exists():
            try:
                with open(fallback_file, 'r') as f:
                    data = json.load(f)

                # Handle domain-partitioned structure
                if "domains" in data:
                    for _domain_name, domain_data in data.get("domains", {}).items():
                        for exp_id, exp in domain_data.get("experiences", {}).items():
                            exp['id'] = exp_id
                            exp_domain = exp.get('domain_context', {}).get('project_type', 'other')

                            # Apply filters
                            if domain and exp_domain != domain:
                                continue

                            retrieval_count = exp.get('retrieval_count', 0)
                            helpful_count = exp.get('helpful_count', 0)
                            helpful_rate = helpful_count / max(retrieval_count, 1)

                            if retrieval_count < min_retrievals:
                                continue
                            if helpful_rate < min_helpful_rate:
                                continue

                            experiences.append(exp)
                            domains_seen.add(exp_domain)
                elif "experiences" in data:
                    # Legacy flat structure
                    for exp_id, exp in data.get("experiences", {}).items():
                        exp['id'] = exp_id
                        experiences.append(exp)
                        domains_seen.add(exp.get('domain_context', {}).get('project_type', 'other'))

            except (json.JSONDecodeError, IOError) as e:
                return ExportResult(
                    success=False,
                    output_path=output_path,
                    experience_count=0,
                    domains_included=[],
                    size_bytes=0,
                    format="jsonl.gz" if compress else "jsonl",
                    checksum="",
                    exported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    filters_applied={"error": str(e)},
                )

        # Write to output file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        content_lines = [json.dumps(exp) for exp in experiences]
        content = "\n".join(content_lines)

        if compress:
            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                f.write(content)
        else:
            with open(output_file, 'w') as f:
                f.write(content)

        # Calculate checksum
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        size_bytes = output_file.stat().st_size

        return ExportResult(
            success=True,
            output_path=str(output_file),
            experience_count=len(experiences),
            domains_included=sorted(list(domains_seen)),
            size_bytes=size_bytes,
            format="jsonl.gz" if compress else "jsonl",
            checksum=checksum,
            exported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            filters_applied={
                "domain": domain,
                "min_helpful_rate": min_helpful_rate,
                "min_retrievals": min_retrievals,
            },
        )

    def purge(self, confirm: bool = False, backup: bool = True) -> PurgeResult:
        """Purge all claude-loop data.

        Args:
            confirm: Must be True to actually purge
            backup: Whether to create backup before purging

        Returns:
            PurgeResult with purge details
        """
        if not confirm:
            return PurgeResult(
                success=False,
                items_removed=0,
                bytes_freed=0,
                locations_cleared=[],
                purged_at="",
                backup_path=None,
            )

        # Calculate current size
        total_size = 0
        total_items = 0
        locations_cleared = []

        claude_loop_dir = self.base_dir / CLAUDE_LOOP_DIR
        backup_path = None

        # Create backup if requested
        if backup and claude_loop_dir.exists():
            backup_name = f"claude-loop-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = self.base_dir / f"{backup_name}.tar.gz"
            try:
                import tarfile
                with tarfile.open(backup_path, "w:gz") as tar:
                    tar.add(claude_loop_dir, arcname=CLAUDE_LOOP_DIR)
            except Exception:
                backup_path = None

        # Count and remove data
        for name, rel_path in DATA_LOCATIONS.items():
            full_path = self.base_dir / rel_path
            if full_path.exists():
                if full_path.is_file():
                    total_size += full_path.stat().st_size
                    total_items += self._count_items(full_path)
                    full_path.unlink()
                    locations_cleared.append(name)
                elif full_path.is_dir():
                    for file_path in full_path.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            total_items += 1
                    shutil.rmtree(full_path)
                    locations_cleared.append(name)

        # Remove config file
        if self.config_file.exists():
            self.config_file.unlink()

        return PurgeResult(
            success=True,
            items_removed=total_items,
            bytes_freed=total_size,
            locations_cleared=locations_cleared,
            purged_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            backup_path=str(backup_path) if backup_path else None,
        )

    def set_mode(
        self,
        mode: PrivacyMode,
        sync_path: Optional[str] = None,
        git_remote: Optional[str] = None,
        agreement_id: Optional[str] = None,
    ) -> bool:
        """Set privacy mode.

        Args:
            mode: Privacy mode to set
            sync_path: Sync path for TEAM_SYNC mode
            git_remote: Git remote for TEAM_SYNC mode
            agreement_id: Agreement ID for FEDERATED mode

        Returns:
            True if successful
        """
        # Validate mode requirements
        if mode == PrivacyMode.TEAM_SYNC:
            if not sync_path and not git_remote:
                print("Error: TEAM_SYNC mode requires --sync-path or --git-remote",
                      file=sys.stderr)
                return False

        if mode == PrivacyMode.FEDERATED:
            if not agreement_id:
                print("Error: FEDERATED mode requires --agreement-id", file=sys.stderr)
                return False

        # Update config
        self.config.mode = mode
        self.config.sync_path = sync_path
        self.config.git_remote = git_remote
        self.config.agreement_id = agreement_id

        # Enforce telemetry/analytics settings
        if mode == PrivacyMode.FULLY_LOCAL:
            self.config.telemetry_enabled = False
            self.config.analytics_enabled = False
        elif mode == PrivacyMode.TEAM_SYNC:
            self.config.telemetry_enabled = False
            self.config.analytics_enabled = False
        # FEDERATED keeps current telemetry settings

        self._save_config()
        return True

    def is_network_allowed(self) -> bool:
        """Check if network calls are allowed in current mode.

        Returns:
            True if network calls are permitted
        """
        if self.config.mode == PrivacyMode.FULLY_LOCAL:
            return False
        if self.config.mode == PrivacyMode.TEAM_SYNC:
            return False  # Only local filesystem or git
        return True  # FEDERATED may allow network

    def is_sharing_allowed(self, data_type: str) -> bool:
        """Check if sharing a data type is allowed in current mode.

        Args:
            data_type: Name of the data type to check

        Returns:
            True if sharing is permitted
        """
        if self.config.mode == PrivacyMode.FULLY_LOCAL:
            return False

        # Check never-share list
        for pattern in NEVER_SHARE:
            if pattern.startswith("*"):
                if data_type.endswith(pattern[1:]):
                    return False
            elif data_type == pattern:
                return False

        # Get location info
        info = self._get_location_info(data_type, self.base_dir / DATA_LOCATIONS.get(data_type, ""))

        if info['sensitive']:
            return False

        return info['shareable']


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_status(args: argparse.Namespace, manager: PrivacyManager) -> int:
    """Show current privacy status and data locations."""
    status = manager.get_status()

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print("Claude-Loop Privacy Status")
        print("=" * 50)
        print(f"\nPrivacy Mode: {status['mode'].upper()}")
        print(f"Description: {status['mode_description']}")
        print(f"\nTelemetry: {'Enabled' if status['telemetry_enabled'] else 'DISABLED'}")
        print(f"Analytics: {'Enabled' if status['analytics_enabled'] else 'DISABLED'}")

        if status['sync_path']:
            print(f"Sync Path: {status['sync_path']}")
        if status['git_remote']:
            print(f"Git Remote: {status['git_remote']}")
        if status['agreement_id']:
            print(f"Agreement ID: {status['agreement_id']}")

        print(f"\nTotal Data Size: {status['total_size_bytes']:,} bytes")
        print(f"Total Files: {status['total_files']}")

        if args.verbose:
            print("\nData Locations:")
            for loc in status['data_locations']:
                if loc['exists']:
                    print(f"  [{loc['name']}]")
                    print(f"    Path: {loc['path']}")
                    print(f"    Size: {loc['size_bytes']:,} bytes")
                    print(f"    Files: {loc['file_count']}")
                    print(f"    Items: {loc['item_count']}")

    return 0


def cmd_audit(args: argparse.Namespace, manager: PrivacyManager) -> int:
    """Run privacy audit and show/export results."""
    report = manager.audit()

    if args.export:
        # Export to file
        output_path = Path(args.export)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Audit report exported to: {output_path}")
        return 0

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("Privacy Audit Report")
        print("=" * 50)
        print(f"Generated: {report.generated_at}")
        print(f"\n{report.summary}")

        print("\nData Locations:")
        for loc in report.data_locations:
            if loc.exists:
                status = "SENSITIVE" if loc.sensitive else ("shareable" if loc.shareable else "local only")
                print(f"  [{loc.name}] - {status}")
                print(f"    Size: {loc.size_bytes:,} bytes | Items: {loc.item_count}")
                print(f"    {loc.description}")

        if report.would_share:
            print(f"\nData that WOULD be shared: {', '.join(report.would_share)}")
        else:
            print("\nData that would be shared: NONE")

        if report.sensitive_data:
            print(f"Sensitive data (never shared): {', '.join(report.sensitive_data)}")

    return 0


def cmd_export(args: argparse.Namespace, manager: PrivacyManager) -> int:
    """Export experiences in portable format."""
    result = manager.export_experiences(
        output_path=args.output,
        domain=args.domain,
        min_helpful_rate=args.min_helpful_rate,
        min_retrievals=args.min_retrievals,
        compress=not args.no_compress,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"Export successful!")
            print(f"  Output: {result.output_path}")
            print(f"  Experiences: {result.experience_count}")
            print(f"  Domains: {', '.join(result.domains_included) if result.domains_included else 'none'}")
            print(f"  Size: {result.size_bytes:,} bytes")
            print(f"  Format: {result.format}")
            print(f"  Checksum: {result.checksum}")
        else:
            print(f"Export failed", file=sys.stderr)
            return 1

    return 0


def cmd_purge(args: argparse.Namespace, manager: PrivacyManager) -> int:
    """Purge all claude-loop data."""
    if not args.confirm:
        print("Error: Use --confirm to actually purge all data", file=sys.stderr)
        print("This will remove ALL claude-loop data including:", file=sys.stderr)
        for name in DATA_LOCATIONS:
            print(f"  - {name}", file=sys.stderr)
        return 1

    result = manager.purge(confirm=True, backup=not args.no_backup)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print("Purge complete!")
            print(f"  Items removed: {result.items_removed}")
            print(f"  Bytes freed: {result.bytes_freed:,}")
            print(f"  Locations cleared: {', '.join(result.locations_cleared)}")
            if result.backup_path:
                print(f"  Backup created: {result.backup_path}")
        else:
            print("Purge cancelled or failed", file=sys.stderr)
            return 1

    return 0


def cmd_set_mode(args: argparse.Namespace, manager: PrivacyManager) -> int:
    """Set privacy mode."""
    try:
        mode = PrivacyMode(args.mode.lower())
    except ValueError:
        print(f"Error: Invalid mode '{args.mode}'. Valid modes: {[m.value for m in PrivacyMode]}",
              file=sys.stderr)
        return 1

    success = manager.set_mode(
        mode=mode,
        sync_path=getattr(args, 'sync_path', None),
        git_remote=getattr(args, 'git_remote', None),
        agreement_id=getattr(args, 'agreement_id', None),
    )

    if success:
        if args.json:
            print(json.dumps({"success": True, "mode": mode.value}))
        else:
            print(f"Privacy mode set to: {mode.value.upper()}")
            if mode == PrivacyMode.FULLY_LOCAL:
                print("  All data will stay local. No network calls enabled.")
            elif mode == PrivacyMode.TEAM_SYNC:
                print(f"  Team sync enabled via: {args.sync_path or args.git_remote}")
            elif mode == PrivacyMode.FEDERATED:
                print(f"  Federated mode with agreement: {args.agreement_id}")
        return 0
    else:
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="Output as JSON")
    parent_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parent_parser.add_argument("--base-dir", default=".", help="Base directory (default: current)")

    # Main parser
    parser = argparse.ArgumentParser(
        description="Privacy-First Local-Only Architecture for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status command
    subparsers.add_parser("status", help="Show current privacy status", parents=[parent_parser])

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Run privacy audit", parents=[parent_parser])
    audit_parser.add_argument("--export", help="Export audit report to file")

    # export command
    export_parser = subparsers.add_parser("export", help="Export experiences", parents=[parent_parser])
    export_parser.add_argument("--output", "-o", required=True, help="Output file path")
    export_parser.add_argument("--domain", help="Filter by domain")
    export_parser.add_argument("--min-helpful-rate", type=float, default=0.0,
                               help="Minimum helpful rate filter")
    export_parser.add_argument("--min-retrievals", type=int, default=0,
                               help="Minimum retrieval count filter")
    export_parser.add_argument("--no-compress", action="store_true",
                               help="Don't compress output")

    # purge command
    purge_parser = subparsers.add_parser("purge", help="Purge all data", parents=[parent_parser])
    purge_parser.add_argument("--confirm", action="store_true",
                              help="Confirm data purge")
    purge_parser.add_argument("--no-backup", action="store_true",
                              help="Skip creating backup before purge")

    # set-mode command
    mode_parser = subparsers.add_parser("set-mode", help="Set privacy mode", parents=[parent_parser])
    mode_parser.add_argument("mode", choices=["fully_local", "team_sync", "federated"],
                             help="Privacy mode to set")
    mode_parser.add_argument("--sync-path", help="Sync path for team_sync mode")
    mode_parser.add_argument("--git-remote", help="Git remote for team_sync mode")
    mode_parser.add_argument("--agreement-id", help="Agreement ID for federated mode")

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = PrivacyManager(base_dir=args.base_dir)

    commands = {
        "status": cmd_status,
        "audit": cmd_audit,
        "export": cmd_export,
        "purge": cmd_purge,
        "set-mode": cmd_set_mode,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, manager)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
