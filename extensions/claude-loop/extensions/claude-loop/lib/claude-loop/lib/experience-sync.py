#!/usr/bin/env python3
# pylint: disable=broad-except
"""
experience-sync.py - Team Experience Sharing (Local Only) for claude-loop

Provides local-only team experience synchronization without any cloud services.
Supports manual export/import, shared folder watching, and git-based sync.

Features:
- Export format: experiences-{domain}-{date}.jsonl.gz (portable)
- Import with deduplication and conflict resolution
- Sync modes: manual export/import, shared folder watch, git-based
- NO cloud sync - only local filesystem or git
- Merge strategy: keep higher helpful_rate version on conflict
- Audit log of all sync operations
- Filtering by domain, min_helpful_rate, min_retrievals

Usage:
    # Export experiences for a specific domain
    python3 lib/experience-sync.py export --domain unity_xr --output ./exports/

    # Export all experiences with quality filters
    python3 lib/experience-sync.py export --min-helpful-rate 0.3 --min-retrievals 5

    # Import experiences from a file
    python3 lib/experience-sync.py import file.jsonl.gz --merge

    # Watch shared folder for sync files
    python3 lib/experience-sync.py sync-folder /shared/team/experiences --watch

    # One-time sync from shared folder
    python3 lib/experience-sync.py sync-folder /shared/team/experiences

    # List sync history
    python3 lib/experience-sync.py history --limit 20

    # Show sync statistics
    python3 lib/experience-sync.py stats

CLI Options:
    --json              Output as JSON
    --verbose           Enable verbose output
    --base-dir          Base directory (default: current)
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Try to import watchdog for file system watching
WATCHDOG_AVAILABLE = False
Observer = None  # type: Any
FileSystemEventHandler = None  # type: Any
FileCreatedEvent = None  # type: Any
try:
    from watchdog.observers import Observer as _Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler as _FileSystemEventHandler  # type: ignore
    from watchdog.events import FileCreatedEvent as _FileCreatedEvent  # type: ignore
    Observer = _Observer
    FileSystemEventHandler = _FileSystemEventHandler
    FileCreatedEvent = _FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Constants
# ============================================================================

CLAUDE_LOOP_DIR = ".claude-loop"
EXPERIENCES_DIR = ".claude-loop/experiences"
SYNC_AUDIT_LOG = ".claude-loop/sync_audit.jsonl"
SYNC_CONFIG_FILE = ".claude-loop/sync_config.json"
EXPORT_DIR = ".claude-loop/exports"

# Export filename pattern: experiences-{domain}-{date}.jsonl.gz
EXPORT_PATTERN = "experiences-{domain}-{date}.jsonl.gz"

# Default similarity threshold for deduplication (higher than retrieval's 0.75)
DEDUP_SIMILARITY_THRESHOLD = 0.90


# ============================================================================
# Enums
# ============================================================================

class SyncMode(str, Enum):
    """Sync mode for experience sharing."""
    MANUAL = "manual"  # Manual export/import
    SHARED_FOLDER = "shared_folder"  # Watch shared folder
    GIT_BASED = "git_based"  # Sync via git repository


class SyncOperation(str, Enum):
    """Types of sync operations."""
    EXPORT = "export"
    IMPORT = "import"
    SYNC = "sync"
    WATCH_START = "watch_start"
    WATCH_STOP = "watch_stop"


class ConflictResolution(str, Enum):
    """How conflicts were resolved."""
    KEPT_LOCAL = "kept_local"  # Local version had higher helpful_rate
    KEPT_REMOTE = "kept_remote"  # Remote version had higher helpful_rate
    MERGED = "merged"  # Counts merged together
    DEDUPLICATED = "deduplicated"  # Skipped as duplicate


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SyncConfig:
    """Sync configuration."""
    mode: SyncMode
    shared_folder_path: Optional[str] = None
    git_remote: Optional[str] = None
    auto_export: bool = False
    auto_import: bool = False
    watch_interval_seconds: int = 60
    export_filters: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data['mode'] = self.mode.value if isinstance(self.mode, SyncMode) else self.mode
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'SyncConfig':
        mode_value = data.get('mode', SyncMode.MANUAL.value)
        if isinstance(mode_value, str):
            try:
                data['mode'] = SyncMode(mode_value)
            except ValueError:
                data['mode'] = SyncMode.MANUAL
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def default(cls) -> 'SyncConfig':
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return cls(mode=SyncMode.MANUAL, created_at=now, updated_at=now)


@dataclass
class ExportedExperience:
    """An experience exported for sharing."""
    id: str
    problem_signature: str
    solution_approach: str
    domain_context: Dict[str, Any]
    success_count: int
    retrieval_count: int
    helpful_count: int
    last_used: str
    created_at: str
    category: str = ""
    tags: List[str] = field(default_factory=list)
    source_machine: str = ""  # Optional: machine identifier
    export_version: str = "1.0"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ExportedExperience':
        # Handle missing fields with defaults
        data.setdefault('category', '')
        data.setdefault('tags', [])
        data.setdefault('source_machine', '')
        data.setdefault('export_version', '1.0')
        data.setdefault('domain_context', {'project_type': 'other'})
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def get_helpful_rate(self) -> float:
        """Calculate helpful rate."""
        if self.retrieval_count == 0:
            return 0.0
        return self.helpful_count / self.retrieval_count


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    output_path: str
    experience_count: int
    domains_included: List[str]
    size_bytes: int
    checksum: str
    exported_at: str
    filters_applied: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    input_path: str
    total_read: int
    imported: int
    skipped_duplicate: int
    conflicts_resolved: int
    conflicts: List[Dict[str, Any]]
    imported_at: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SyncAuditEntry:
    """Audit log entry for a sync operation."""
    operation: str
    timestamp: str
    path: str
    experience_count: int
    domains: List[str]
    duration_ms: int
    success: bool
    details: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConflictDetail:
    """Details about a conflict resolution."""
    experience_id: str
    local_helpful_rate: float
    remote_helpful_rate: float
    resolution: ConflictResolution
    merged_counts: Optional[Dict[str, int]] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data['resolution'] = self.resolution.value if isinstance(self.resolution, ConflictResolution) else self.resolution
        return data


@dataclass
class SyncStats:
    """Statistics about sync operations."""
    total_exports: int
    total_imports: int
    total_experiences_exported: int
    total_experiences_imported: int
    total_conflicts_resolved: int
    total_duplicates_skipped: int
    last_export: Optional[str]
    last_import: Optional[str]
    domains_synced: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Experience Sync Manager
# ============================================================================

class ExperienceSyncManager:
    """
    Manages team experience synchronization.

    Supports manual export/import, shared folder watching, and git-based sync.
    All operations are local-only with no cloud services.
    """

    def __init__(self, base_dir: str = "."):
        """Initialize the sync manager.

        Args:
            base_dir: Base directory for claude-loop
        """
        self.base_dir = Path(base_dir)
        self.experiences_dir = self.base_dir / EXPERIENCES_DIR
        self.audit_log_path = self.base_dir / SYNC_AUDIT_LOG
        self.config_path = self.base_dir / SYNC_CONFIG_FILE
        self.export_dir = self.base_dir / EXPORT_DIR
        self.fallback_file = self.experiences_dir / "experiences_fallback.json"

        self.config = self._load_config()
        self._ensure_dirs()

        # File system watcher (if watchdog available)
        self.observer: Optional[Any] = None

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.experiences_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> SyncConfig:
        """Load sync configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    return SyncConfig.from_dict(data)
            except (json.JSONDecodeError, IOError):
                pass
        return SyncConfig.default()

    def _save_config(self) -> None:
        """Save sync configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.updated_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        with open(self.config_path, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)

    def _log_audit(self, entry: SyncAuditEntry) -> None:
        """Append an audit entry to the log."""
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def _load_local_experiences(self) -> Dict[str, Dict[str, Any]]:
        """Load all local experiences from fallback JSON storage.

        Returns:
            Dictionary mapping experience_id -> experience_data
        """
        experiences = {}
        if not self.fallback_file.exists():
            return experiences

        try:
            with open(self.fallback_file, 'r') as f:
                data = json.load(f)

            # Handle domain-partitioned structure
            if "domains" in data:
                for domain_data in data.get("domains", {}).values():
                    for exp_id, exp in domain_data.get("experiences", {}).items():
                        exp_copy = dict(exp)
                        exp_copy['id'] = exp_id
                        experiences[exp_id] = exp_copy
            elif "experiences" in data:
                # Legacy flat structure
                for exp_id, exp in data.get("experiences", {}).items():
                    exp_copy = dict(exp)
                    exp_copy['id'] = exp_id
                    experiences[exp_id] = exp_copy

        except (json.JSONDecodeError, IOError):
            pass

        return experiences

    def _save_local_experiences(self, experiences: Dict[str, Dict[str, Any]]) -> None:
        """Save experiences back to local storage.

        Args:
            experiences: Dictionary mapping experience_id -> experience_data
        """
        # Load existing structure to preserve domain partitioning
        existing_data = {"domains": {}}
        if self.fallback_file.exists():
            try:
                with open(self.fallback_file, 'r') as f:
                    existing_data = json.load(f)
                    if "domains" not in existing_data:
                        existing_data = {"domains": {"other": existing_data}}
            except (json.JSONDecodeError, IOError):
                pass

        # Clear existing experiences but keep structure
        for domain_data in existing_data.get("domains", {}).values():
            domain_data["experiences"] = {}

        # Re-populate with updated experiences
        for exp_id, exp in experiences.items():
            domain = exp.get('domain_context', {}).get('project_type', 'other')
            parent = self._get_parent_category(domain)

            if parent not in existing_data["domains"]:
                existing_data["domains"][parent] = {"experiences": {}, "embeddings": {}}

            # Remove 'id' from data before storing (it's the key)
            exp_data = {k: v for k, v in exp.items() if k != 'id'}
            existing_data["domains"][parent]["experiences"][exp_id] = exp_data

        self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.fallback_file, 'w') as f:
            json.dump(existing_data, f, indent=2)

    def _get_parent_category(self, domain: str) -> str:
        """Get parent category for a domain type."""
        parent_map = {
            "web_frontend": "web",
            "web_backend": "web",
            "unity_game": "unity",
            "unity_xr": "unity",
            "isaac_sim": "simulation",
            "ml_training": "ml",
            "ml_inference": "ml",
            "data_pipeline": "data",
            "cli_tool": "cli",
            "robotics": "physical",
            "other": "other",
        }
        return parent_map.get(domain, "other")

    def _generate_export_filename(self, domain: Optional[str] = None, compress: bool = True) -> str:
        """Generate export filename using pattern.

        Args:
            domain: Domain filter (or 'all' if not filtered)
            compress: Whether the file will be compressed

        Returns:
            Filename following pattern: experiences-{domain}-{date}.jsonl[.gz]
        """
        domain_str = domain if domain else "all"
        date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = EXPORT_PATTERN.format(domain=domain_str, date=date_str)
        if not compress:
            # Remove .gz suffix
            base_filename = base_filename.replace('.jsonl.gz', '.jsonl')
        return base_filename

    def _compute_similarity(self, exp1: Dict[str, Any], exp2: Dict[str, Any]) -> float:
        """Compute text similarity between two experiences.

        Uses simple string comparison for problem signatures.
        Returns value between 0 and 1.
        """
        from difflib import SequenceMatcher

        prob1 = exp1.get('problem_signature', '')
        prob2 = exp2.get('problem_signature', '')

        return SequenceMatcher(None, prob1, prob2).ratio()

    def export_experiences(
        self,
        output_path: Optional[str] = None,
        domain: Optional[str] = None,
        min_helpful_rate: float = 0.0,
        min_retrievals: int = 0,
        compress: bool = True,
    ) -> ExportResult:
        """Export experiences in portable format.

        Args:
            output_path: Output file path (auto-generated if None)
            domain: Filter by domain type
            min_helpful_rate: Minimum helpful rate filter
            min_retrievals: Minimum retrieval count filter
            compress: Whether to gzip compress (default True)

        Returns:
            ExportResult with export details
        """
        start_time = time.time()

        # Generate output path if not provided
        if output_path is None:
            filename = self._generate_export_filename(domain, compress=compress)
            output_path = str(self.export_dir / filename)

        # Ensure directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Load and filter experiences
        local_experiences = self._load_local_experiences()
        filtered_experiences: List[ExportedExperience] = []
        domains_seen: Set[str] = set()

        for exp_id, exp in local_experiences.items():
            exp_domain = exp.get('domain_context', {}).get('project_type', 'other')

            # Apply domain filter
            if domain and exp_domain != domain:
                continue

            # Apply quality filters
            retrieval_count = exp.get('retrieval_count', 0)
            helpful_count = exp.get('helpful_count', 0)
            helpful_rate = helpful_count / max(retrieval_count, 1)

            if retrieval_count < min_retrievals:
                continue
            if helpful_rate < min_helpful_rate:
                continue

            # Convert to ExportedExperience
            exported = ExportedExperience(
                id=exp_id,
                problem_signature=exp.get('problem_signature', ''),
                solution_approach=exp.get('solution_approach', ''),
                domain_context=exp.get('domain_context', {'project_type': 'other'}),
                success_count=exp.get('success_count', 0),
                retrieval_count=retrieval_count,
                helpful_count=helpful_count,
                last_used=exp.get('last_used', ''),
                created_at=exp.get('created_at', ''),
                category=exp.get('category', ''),
                tags=exp.get('tags', []),
                source_machine=os.uname().nodename if hasattr(os, 'uname') else '',
            )
            filtered_experiences.append(exported)
            domains_seen.add(exp_domain)

        # Write to file
        try:
            content_lines = [json.dumps(exp.to_dict()) for exp in filtered_experiences]
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

            # Log audit
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_audit(SyncAuditEntry(
                operation=SyncOperation.EXPORT.value,
                timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                path=str(output_file),
                experience_count=len(filtered_experiences),
                domains=sorted(list(domains_seen)),
                duration_ms=duration_ms,
                success=True,
                details={
                    "filters": {
                        "domain": domain,
                        "min_helpful_rate": min_helpful_rate,
                        "min_retrievals": min_retrievals,
                    },
                    "checksum": checksum,
                },
            ))

            return ExportResult(
                success=True,
                output_path=str(output_file),
                experience_count=len(filtered_experiences),
                domains_included=sorted(list(domains_seen)),
                size_bytes=size_bytes,
                checksum=checksum,
                exported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                filters_applied={
                    "domain": domain,
                    "min_helpful_rate": min_helpful_rate,
                    "min_retrievals": min_retrievals,
                    "compressed": compress,
                },
            )

        except Exception as e:
            # Log failed audit
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_audit(SyncAuditEntry(
                operation=SyncOperation.EXPORT.value,
                timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                path=str(output_file),
                experience_count=0,
                domains=[],
                duration_ms=duration_ms,
                success=False,
                details={},
                error=str(e),
            ))

            return ExportResult(
                success=False,
                output_path=str(output_file),
                experience_count=0,
                domains_included=[],
                size_bytes=0,
                checksum="",
                exported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                filters_applied={},
                error=str(e),
            )

    def import_experiences(
        self,
        input_path: str,
        merge: bool = True,
        dry_run: bool = False,
    ) -> ImportResult:
        """Import experiences from a file with deduplication and conflict resolution.

        Merge strategy: keep higher helpful_rate version on conflict.

        Args:
            input_path: Path to import file (.jsonl or .jsonl.gz)
            merge: Whether to merge with existing (True) or replace (False)
            dry_run: If True, only report what would happen

        Returns:
            ImportResult with import details
        """
        start_time = time.time()
        input_file = Path(input_path)

        if not input_file.exists():
            return ImportResult(
                success=False,
                input_path=str(input_file),
                total_read=0,
                imported=0,
                skipped_duplicate=0,
                conflicts_resolved=0,
                conflicts=[],
                imported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                error=f"File not found: {input_path}",
            )

        # Load imported experiences
        imported_experiences: List[ExportedExperience] = []
        try:
            # Determine if gzipped
            if input_file.suffix == '.gz' or input_file.name.endswith('.jsonl.gz'):
                with gzip.open(input_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            imported_experiences.append(ExportedExperience.from_dict(data))
            else:
                with open(input_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            imported_experiences.append(ExportedExperience.from_dict(data))
        except Exception as e:
            return ImportResult(
                success=False,
                input_path=str(input_file),
                total_read=0,
                imported=0,
                skipped_duplicate=0,
                conflicts_resolved=0,
                conflicts=[],
                imported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                error=f"Failed to read file: {e}",
            )

        # Load local experiences
        local_experiences = self._load_local_experiences() if merge else {}

        # Process imports
        imported_count = 0
        skipped_duplicate = 0
        conflicts_resolved = 0
        conflicts: List[Dict[str, Any]] = []
        domains_seen: Set[str] = set()

        for imported_exp in imported_experiences:
            exp_domain = imported_exp.domain_context.get('project_type', 'other')
            domains_seen.add(exp_domain)

            # Check for exact ID match (conflict)
            if imported_exp.id in local_experiences:
                local_exp = local_experiences[imported_exp.id]
                local_rate = local_exp.get('helpful_count', 0) / max(local_exp.get('retrieval_count', 1), 1)
                remote_rate = imported_exp.get_helpful_rate()

                # Merge strategy: keep higher helpful_rate
                if remote_rate > local_rate:
                    # Keep remote
                    if not dry_run:
                        local_experiences[imported_exp.id] = imported_exp.to_dict()
                    conflicts.append(ConflictDetail(
                        experience_id=imported_exp.id,
                        local_helpful_rate=local_rate,
                        remote_helpful_rate=remote_rate,
                        resolution=ConflictResolution.KEPT_REMOTE,
                    ).to_dict())
                    imported_count += 1
                else:
                    # Keep local
                    conflicts.append(ConflictDetail(
                        experience_id=imported_exp.id,
                        local_helpful_rate=local_rate,
                        remote_helpful_rate=remote_rate,
                        resolution=ConflictResolution.KEPT_LOCAL,
                    ).to_dict())

                conflicts_resolved += 1
                continue

            # Check for similar experiences (deduplication)
            is_duplicate = False
            for local_id, local_exp in local_experiences.items():
                similarity = self._compute_similarity(imported_exp.to_dict(), local_exp)
                if similarity >= DEDUP_SIMILARITY_THRESHOLD:
                    # Very similar - check domain match
                    local_domain = local_exp.get('domain_context', {}).get('project_type', 'other')
                    if local_domain == exp_domain:
                        # Same domain and very similar - deduplicate
                        local_rate = local_exp.get('helpful_count', 0) / max(local_exp.get('retrieval_count', 1), 1)
                        remote_rate = imported_exp.get_helpful_rate()

                        if remote_rate > local_rate:
                            # Remote is better - replace
                            if not dry_run:
                                del local_experiences[local_id]
                                local_experiences[imported_exp.id] = imported_exp.to_dict()
                            conflicts.append(ConflictDetail(
                                experience_id=imported_exp.id,
                                local_helpful_rate=local_rate,
                                remote_helpful_rate=remote_rate,
                                resolution=ConflictResolution.DEDUPLICATED,
                            ).to_dict())
                        else:
                            skipped_duplicate += 1

                        is_duplicate = True
                        break

            if not is_duplicate:
                # New experience - add it
                if not dry_run:
                    local_experiences[imported_exp.id] = imported_exp.to_dict()
                imported_count += 1

        # Save updated experiences
        if not dry_run and (imported_count > 0 or conflicts_resolved > 0):
            self._save_local_experiences(local_experiences)

        # Log audit
        duration_ms = int((time.time() - start_time) * 1000)
        self._log_audit(SyncAuditEntry(
            operation=SyncOperation.IMPORT.value,
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            path=str(input_file),
            experience_count=imported_count,
            domains=sorted(list(domains_seen)),
            duration_ms=duration_ms,
            success=True,
            details={
                "total_read": len(imported_experiences),
                "imported": imported_count,
                "skipped_duplicate": skipped_duplicate,
                "conflicts_resolved": conflicts_resolved,
                "dry_run": dry_run,
            },
        ))

        return ImportResult(
            success=True,
            input_path=str(input_file),
            total_read=len(imported_experiences),
            imported=imported_count,
            skipped_duplicate=skipped_duplicate,
            conflicts_resolved=conflicts_resolved,
            conflicts=conflicts,
            imported_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        )

    def sync_folder(
        self,
        folder_path: str,
        watch: bool = False,
        export_on_sync: bool = True,
        import_existing: bool = True,
    ) -> Dict[str, Any]:
        """Sync experiences with a shared folder.

        Args:
            folder_path: Path to shared folder
            watch: If True, start watching for changes
            export_on_sync: Export local experiences to shared folder
            import_existing: Import existing files from shared folder

        Returns:
            Dictionary with sync results
        """
        folder = Path(folder_path)
        folder.mkdir(parents=True, exist_ok=True)

        results = {
            "folder": str(folder),
            "watch_started": False,
            "export_result": None,
            "import_results": [],
            "files_found": [],
        }

        # Export local experiences to shared folder
        if export_on_sync:
            export_result = self.export_experiences(
                output_path=str(folder / self._generate_export_filename()),
            )
            results["export_result"] = export_result.to_dict()

        # Import existing files from shared folder
        if import_existing:
            for file_path in folder.glob("*.jsonl*"):
                if file_path.is_file():
                    results["files_found"].append(str(file_path))
                    import_result = self.import_experiences(str(file_path), merge=True)
                    results["import_results"].append(import_result.to_dict())

        # Start watching if requested
        if watch and WATCHDOG_AVAILABLE:
            self._start_folder_watch(folder)
            results["watch_started"] = True

            # Update config
            self.config.mode = SyncMode.SHARED_FOLDER
            self.config.shared_folder_path = str(folder)
            self._save_config()

            # Log audit
            self._log_audit(SyncAuditEntry(
                operation=SyncOperation.WATCH_START.value,
                timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                path=str(folder),
                experience_count=0,
                domains=[],
                duration_ms=0,
                success=True,
                details={"watch_interval": self.config.watch_interval_seconds},
            ))

        elif watch and not WATCHDOG_AVAILABLE:
            results["watch_started"] = False
            results["watch_error"] = "watchdog package not available. Install with: pip install watchdog"

        return results

    def _start_folder_watch(self, folder: Path) -> None:
        """Start watching a folder for new sync files.

        Args:
            folder: Folder to watch
        """
        if not WATCHDOG_AVAILABLE or Observer is None or FileSystemEventHandler is None:
            return

        # Stop existing watcher if any
        self.stop_watching()

        # Create handler class dynamically since base class may not be available
        handler_base = FileSystemEventHandler  # type: Any

        class SyncFileHandler(handler_base):  # type: ignore
            def __init__(self, manager: 'ExperienceSyncManager'):
                super().__init__()
                self.manager = manager

            def on_created(self, event: Any) -> None:
                if FileCreatedEvent is not None and isinstance(event, FileCreatedEvent):
                    file_path = Path(event.src_path)
                    if file_path.suffix in ['.jsonl', '.gz'] and file_path.is_file():
                        # Wait a moment for file to be fully written
                        time.sleep(0.5)
                        self.manager.import_experiences(str(file_path), merge=True)

        self.observer = Observer()  # type: ignore
        if self.observer is not None:
            self.observer.schedule(SyncFileHandler(self), str(folder), recursive=False)
            self.observer.start()

    def stop_watching(self) -> None:
        """Stop watching for folder changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

            # Log audit
            self._log_audit(SyncAuditEntry(
                operation=SyncOperation.WATCH_STOP.value,
                timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                path=self.config.shared_folder_path or "",
                experience_count=0,
                domains=[],
                duration_ms=0,
                success=True,
                details={},
            ))

    def get_sync_history(self, limit: int = 50) -> List[SyncAuditEntry]:
        """Get sync operation history from audit log.

        Args:
            limit: Maximum entries to return

        Returns:
            List of audit entries (most recent first)
        """
        entries: List[SyncAuditEntry] = []

        if not self.audit_log_path.exists():
            return entries

        try:
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        entries.append(SyncAuditEntry(**data))
        except (json.JSONDecodeError, IOError):
            pass

        # Return most recent first
        entries.reverse()
        return entries[:limit]

    def get_sync_stats(self) -> SyncStats:
        """Get sync statistics from audit log.

        Returns:
            SyncStats with aggregated statistics
        """
        history = self.get_sync_history(limit=1000)

        total_exports = 0
        total_imports = 0
        total_exp_exported = 0
        total_exp_imported = 0
        total_conflicts = 0
        total_duplicates = 0
        last_export: Optional[str] = None
        last_import: Optional[str] = None
        domains: Set[str] = set()

        for entry in history:
            if entry.operation == SyncOperation.EXPORT.value:
                total_exports += 1
                total_exp_exported += entry.experience_count
                if last_export is None:
                    last_export = entry.timestamp
            elif entry.operation == SyncOperation.IMPORT.value:
                total_imports += 1
                total_exp_imported += entry.details.get('imported', 0)
                total_conflicts += entry.details.get('conflicts_resolved', 0)
                total_duplicates += entry.details.get('skipped_duplicate', 0)
                if last_import is None:
                    last_import = entry.timestamp

            domains.update(entry.domains)

        return SyncStats(
            total_exports=total_exports,
            total_imports=total_imports,
            total_experiences_exported=total_exp_exported,
            total_experiences_imported=total_exp_imported,
            total_conflicts_resolved=total_conflicts,
            total_duplicates_skipped=total_duplicates,
            last_export=last_export,
            last_import=last_import,
            domains_synced=sorted(list(domains)),
        )


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_export(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Export experiences to file."""
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
            print(f"  Checksum: {result.checksum}")
        else:
            print(f"Export failed: {result.error}", file=sys.stderr)
            return 1

    return 0


def cmd_import(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Import experiences from file."""
    result = manager.import_experiences(
        input_path=args.file,
        merge=args.merge,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"Import {'(dry run) ' if args.dry_run else ''}successful!")
            print(f"  Input: {result.input_path}")
            print(f"  Total read: {result.total_read}")
            print(f"  Imported: {result.imported}")
            print(f"  Skipped (duplicate): {result.skipped_duplicate}")
            print(f"  Conflicts resolved: {result.conflicts_resolved}")

            if result.conflicts and args.verbose:
                print("\n  Conflict Details:")
                for conflict in result.conflicts[:10]:
                    print(f"    [{conflict['experience_id']}]")
                    print(f"      Local rate: {conflict['local_helpful_rate']:.2%}")
                    print(f"      Remote rate: {conflict['remote_helpful_rate']:.2%}")
                    print(f"      Resolution: {conflict['resolution']}")
                if len(result.conflicts) > 10:
                    print(f"    ... and {len(result.conflicts) - 10} more")
        else:
            print(f"Import failed: {result.error}", file=sys.stderr)
            return 1

    return 0


def cmd_sync_folder(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Sync with a shared folder."""
    result = manager.sync_folder(
        folder_path=args.path,
        watch=args.watch,
        export_on_sync=not args.no_export,
        import_existing=not args.no_import,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Sync folder: {result['folder']}")

        if result.get('export_result'):
            exp_result = result['export_result']
            if exp_result['success']:
                print(f"  Exported {exp_result['experience_count']} experiences")

        import_count = sum(r['imported'] for r in result.get('import_results', []))
        if import_count:
            print(f"  Imported {import_count} experiences from {len(result.get('files_found', []))} files")

        if result.get('watch_started'):
            print(f"\n  Watching for changes... (Ctrl+C to stop)")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                manager.stop_watching()
                print("\n  Watch stopped.")
        elif args.watch and result.get('watch_error'):
            print(f"  Watch error: {result['watch_error']}", file=sys.stderr)

    return 0


def cmd_history(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Show sync history."""
    history = manager.get_sync_history(limit=args.limit)

    if args.json:
        print(json.dumps([e.to_dict() for e in history], indent=2))
    else:
        if not history:
            print("No sync history found")
            return 0

        print(f"Sync History (last {len(history)} operations):")
        for entry in history:
            status = "OK" if entry.success else "FAILED"
            print(f"\n  [{entry.operation.upper()}] {entry.timestamp} - {status}")
            print(f"    Path: {entry.path}")
            print(f"    Experiences: {entry.experience_count}")
            if entry.domains:
                print(f"    Domains: {', '.join(entry.domains)}")
            print(f"    Duration: {entry.duration_ms}ms")
            if entry.error:
                print(f"    Error: {entry.error}")

    return 0


def cmd_stats(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Show sync statistics."""
    stats = manager.get_sync_stats()

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2))
    else:
        print("Sync Statistics:")
        print(f"  Total exports: {stats.total_exports}")
        print(f"  Total imports: {stats.total_imports}")
        print(f"  Experiences exported: {stats.total_experiences_exported}")
        print(f"  Experiences imported: {stats.total_experiences_imported}")
        print(f"  Conflicts resolved: {stats.total_conflicts_resolved}")
        print(f"  Duplicates skipped: {stats.total_duplicates_skipped}")
        if stats.last_export:
            print(f"  Last export: {stats.last_export}")
        if stats.last_import:
            print(f"  Last import: {stats.last_import}")
        if stats.domains_synced:
            print(f"  Domains synced: {', '.join(stats.domains_synced)}")

    return 0


def cmd_config(args: argparse.Namespace, manager: ExperienceSyncManager) -> int:
    """Show or update sync configuration."""
    if args.json:
        print(json.dumps(manager.config.to_dict(), indent=2))
    else:
        print("Sync Configuration:")
        print(f"  Mode: {manager.config.mode.value}")
        if manager.config.shared_folder_path:
            print(f"  Shared folder: {manager.config.shared_folder_path}")
        if manager.config.git_remote:
            print(f"  Git remote: {manager.config.git_remote}")
        print(f"  Auto export: {manager.config.auto_export}")
        print(f"  Auto import: {manager.config.auto_import}")
        print(f"  Watch interval: {manager.config.watch_interval_seconds}s")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="Output as JSON")
    parent_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parent_parser.add_argument("--base-dir", default=".", help="Base directory (default: current)")

    # Main parser
    parser = argparse.ArgumentParser(
        description="Team Experience Sharing (Local Only) for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # export command
    export_parser = subparsers.add_parser(
        "export", help="Export experiences to file", parents=[parent_parser]
    )
    export_parser.add_argument("--output", "-o", help="Output file path (auto-generated if not specified)")
    export_parser.add_argument("--domain", "-d", help="Filter by domain type")
    export_parser.add_argument("--min-helpful-rate", type=float, default=0.0,
                               help="Minimum helpful rate filter (0.0-1.0)")
    export_parser.add_argument("--min-retrievals", type=int, default=0,
                               help="Minimum retrieval count filter")
    export_parser.add_argument("--no-compress", action="store_true",
                               help="Don't compress output")

    # import command
    import_parser = subparsers.add_parser(
        "import", help="Import experiences from file", parents=[parent_parser]
    )
    import_parser.add_argument("file", help="File to import (.jsonl or .jsonl.gz)")
    import_parser.add_argument("--merge", action="store_true", default=True,
                               help="Merge with existing experiences (default)")
    import_parser.add_argument("--replace", dest="merge", action="store_false",
                               help="Replace existing experiences")
    import_parser.add_argument("--dry-run", action="store_true",
                               help="Only report what would happen")

    # sync-folder command
    sync_parser = subparsers.add_parser(
        "sync-folder", help="Sync with shared folder", parents=[parent_parser]
    )
    sync_parser.add_argument("path", help="Path to shared folder")
    sync_parser.add_argument("--watch", "-w", action="store_true",
                             help="Watch for changes continuously")
    sync_parser.add_argument("--no-export", action="store_true",
                             help="Don't export local experiences")
    sync_parser.add_argument("--no-import", action="store_true",
                             help="Don't import existing files")

    # history command
    history_parser = subparsers.add_parser(
        "history", help="Show sync history", parents=[parent_parser]
    )
    history_parser.add_argument("--limit", "-l", type=int, default=20,
                                help="Maximum entries to show")

    # stats command
    subparsers.add_parser("stats", help="Show sync statistics", parents=[parent_parser])

    # config command
    subparsers.add_parser("config", help="Show sync configuration", parents=[parent_parser])

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = ExperienceSyncManager(base_dir=args.base_dir)

    commands = {
        "export": cmd_export,
        "import": cmd_import,
        "sync-folder": cmd_sync_folder,
        "history": cmd_history,
        "stats": cmd_stats,
        "config": cmd_config,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, manager)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
