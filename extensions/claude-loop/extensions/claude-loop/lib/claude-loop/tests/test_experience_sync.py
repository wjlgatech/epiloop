#!/usr/bin/env python3
"""
Tests for experience-sync.py - Team Experience Sharing (Local Only)

Tests cover:
- Export functionality with domain and quality filters
- Import with deduplication and conflict resolution
- Merge strategy (keep higher helpful_rate)
- Audit logging
- Sync statistics
- File format (experiences-{domain}-{date}.jsonl.gz)
"""

import gzip
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add the lib directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Import using runpy to handle hyphenated filename
import runpy
experience_sync = runpy.run_path(str(Path(__file__).parent.parent / "lib" / "experience-sync.py"))

# Extract classes and functions
ExperienceSyncManager = experience_sync['ExperienceSyncManager']
ExportedExperience = experience_sync['ExportedExperience']
ExportResult = experience_sync['ExportResult']
ImportResult = experience_sync['ImportResult']
SyncAuditEntry = experience_sync['SyncAuditEntry']
SyncConfig = experience_sync['SyncConfig']
SyncMode = experience_sync['SyncMode']
SyncOperation = experience_sync['SyncOperation']
ConflictResolution = experience_sync['ConflictResolution']
ConflictDetail = experience_sync['ConflictDetail']
SyncStats = experience_sync['SyncStats']
DEDUP_SIMILARITY_THRESHOLD = experience_sync['DEDUP_SIMILARITY_THRESHOLD']


class TestExportedExperience(unittest.TestCase):
    """Tests for ExportedExperience dataclass."""

    def test_create_experience(self):
        """Test creating an exported experience."""
        exp = ExportedExperience(
            id="test123",
            problem_signature="Test problem",
            solution_approach="Test solution",
            domain_context={"project_type": "unity_xr"},
            success_count=5,
            retrieval_count=10,
            helpful_count=7,
            last_used="2026-01-12T00:00:00Z",
            created_at="2026-01-10T00:00:00Z",
        )
        self.assertEqual(exp.id, "test123")
        self.assertEqual(exp.get_helpful_rate(), 0.7)

    def test_helpful_rate_zero_retrievals(self):
        """Test helpful rate with zero retrievals."""
        exp = ExportedExperience(
            id="test123",
            problem_signature="Test problem",
            solution_approach="Test solution",
            domain_context={"project_type": "unity_xr"},
            success_count=5,
            retrieval_count=0,
            helpful_count=0,
            last_used="2026-01-12T00:00:00Z",
            created_at="2026-01-10T00:00:00Z",
        )
        self.assertEqual(exp.get_helpful_rate(), 0.0)

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        exp = ExportedExperience(
            id="test123",
            problem_signature="Test problem",
            solution_approach="Test solution",
            domain_context={"project_type": "unity_xr"},
            success_count=5,
            retrieval_count=10,
            helpful_count=7,
            last_used="2026-01-12T00:00:00Z",
            created_at="2026-01-10T00:00:00Z",
            category="test_category",
            tags=["tag1", "tag2"],
        )

        data = exp.to_dict()
        restored = ExportedExperience.from_dict(data)

        self.assertEqual(restored.id, exp.id)
        self.assertEqual(restored.problem_signature, exp.problem_signature)
        self.assertEqual(restored.category, exp.category)
        self.assertEqual(restored.tags, exp.tags)


class TestSyncConfig(unittest.TestCase):
    """Tests for SyncConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = SyncConfig.default()
        self.assertEqual(config.mode, SyncMode.MANUAL)
        self.assertFalse(config.auto_export)
        self.assertFalse(config.auto_import)

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        config = SyncConfig(
            mode=SyncMode.SHARED_FOLDER,
            shared_folder_path="/shared/folder",
            watch_interval_seconds=120,
        )

        data = config.to_dict()
        restored = SyncConfig.from_dict(data)

        self.assertEqual(restored.mode, SyncMode.SHARED_FOLDER)
        self.assertEqual(restored.shared_folder_path, "/shared/folder")
        self.assertEqual(restored.watch_interval_seconds, 120)


class TestExperienceSyncManager(unittest.TestCase):
    """Tests for ExperienceSyncManager class."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = ExperienceSyncManager(base_dir=self.test_dir)

        # Create some test experiences in the fallback storage
        self._create_test_experiences()

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_experiences(self):
        """Create test experiences in fallback storage."""
        experiences_dir = Path(self.test_dir) / ".claude-loop" / "experiences"
        experiences_dir.mkdir(parents=True, exist_ok=True)

        fallback_data = {
            "domains": {
                "unity": {
                    "experiences": {
                        "exp001": {
                            "problem_signature": "Unity XR element not found",
                            "solution_approach": "Use FindObjectOfType with includeInactive",
                            "domain_context": {"project_type": "unity_xr", "language": "csharp"},
                            "success_count": 5,
                            "retrieval_count": 10,
                            "helpful_count": 8,
                            "last_used": "2026-01-12T00:00:00Z",
                            "created_at": "2026-01-10T00:00:00Z",
                            "category": "UI",
                            "tags": ["unity", "xr"],
                        },
                        "exp002": {
                            "problem_signature": "Unity shader compile error",
                            "solution_approach": "Check shader target level",
                            "domain_context": {"project_type": "unity_game", "language": "hlsl"},
                            "success_count": 3,
                            "retrieval_count": 5,
                            "helpful_count": 2,
                            "last_used": "2026-01-11T00:00:00Z",
                            "created_at": "2026-01-09T00:00:00Z",
                            "category": "Shader",
                            "tags": ["unity", "shader"],
                        },
                    },
                    "embeddings": {},
                },
                "web": {
                    "experiences": {
                        "exp003": {
                            "problem_signature": "React component not rendering",
                            "solution_approach": "Check useEffect dependencies",
                            "domain_context": {"project_type": "web_frontend", "language": "typescript"},
                            "success_count": 10,
                            "retrieval_count": 20,
                            "helpful_count": 15,
                            "last_used": "2026-01-12T00:00:00Z",
                            "created_at": "2026-01-08T00:00:00Z",
                            "category": "React",
                            "tags": ["react", "hooks"],
                        },
                    },
                    "embeddings": {},
                },
            }
        }

        fallback_file = experiences_dir / "experiences_fallback.json"
        with open(fallback_file, 'w') as f:
            json.dump(fallback_data, f)

    def test_export_all_experiences(self):
        """Test exporting all experiences."""
        result = self.manager.export_experiences()

        self.assertTrue(result.success)
        self.assertEqual(result.experience_count, 3)
        self.assertIn("unity_xr", result.domains_included)
        self.assertIn("web_frontend", result.domains_included)
        self.assertTrue(result.output_path.endswith(".jsonl.gz"))
        self.assertTrue(os.path.exists(result.output_path))

    def test_export_domain_filter(self):
        """Test exporting with domain filter."""
        result = self.manager.export_experiences(domain="unity_xr")

        self.assertTrue(result.success)
        self.assertEqual(result.experience_count, 1)
        self.assertEqual(result.domains_included, ["unity_xr"])

    def test_export_helpful_rate_filter(self):
        """Test exporting with helpful rate filter."""
        # exp001: 80%, exp002: 40%, exp003: 75%
        result = self.manager.export_experiences(min_helpful_rate=0.7)

        self.assertTrue(result.success)
        self.assertEqual(result.experience_count, 2)  # exp001 and exp003

    def test_export_retrieval_filter(self):
        """Test exporting with retrieval count filter."""
        # exp001: 10, exp002: 5, exp003: 20
        result = self.manager.export_experiences(min_retrievals=10)

        self.assertTrue(result.success)
        self.assertEqual(result.experience_count, 2)  # exp001 and exp003

    def test_export_combined_filters(self):
        """Test exporting with multiple filters."""
        result = self.manager.export_experiences(
            min_helpful_rate=0.7,
            min_retrievals=15,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.experience_count, 1)  # Only exp003

    def test_export_uncompressed(self):
        """Test exporting without compression."""
        result = self.manager.export_experiences(compress=False)

        self.assertTrue(result.success)
        self.assertTrue(result.output_path.endswith(".jsonl"))
        self.assertFalse(result.output_path.endswith(".gz"))

    def test_export_filename_pattern(self):
        """Test export filename follows pattern."""
        result = self.manager.export_experiences(domain="unity_xr")

        # Should match: experiences-unity_xr-YYYYMMDD-HHMMSS.jsonl.gz
        filename = os.path.basename(result.output_path)
        self.assertTrue(filename.startswith("experiences-unity_xr-"))
        self.assertTrue(filename.endswith(".jsonl.gz"))

    def test_import_new_experiences(self):
        """Test importing new experiences."""
        # Create an export file with new experiences
        export_file = self._create_import_file([
            {
                "id": "new001",
                "problem_signature": "New problem 1",
                "solution_approach": "New solution 1",
                "domain_context": {"project_type": "ml_training"},
                "success_count": 5,
                "retrieval_count": 10,
                "helpful_count": 8,
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        result = self.manager.import_experiences(export_file)

        self.assertTrue(result.success)
        self.assertEqual(result.total_read, 1)
        self.assertEqual(result.imported, 1)
        self.assertEqual(result.skipped_duplicate, 0)
        self.assertEqual(result.conflicts_resolved, 0)

    def test_import_conflict_keep_higher_rate(self):
        """Test conflict resolution keeps higher helpful_rate."""
        # Create import with same ID but higher helpful rate
        export_file = self._create_import_file([
            {
                "id": "exp001",  # Same ID as existing
                "problem_signature": "Unity XR element not found",
                "solution_approach": "Better solution",
                "domain_context": {"project_type": "unity_xr", "language": "csharp"},
                "success_count": 20,
                "retrieval_count": 20,
                "helpful_count": 19,  # 95% vs existing 80%
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        result = self.manager.import_experiences(export_file)

        self.assertTrue(result.success)
        self.assertEqual(result.conflicts_resolved, 1)
        self.assertEqual(result.imported, 1)

        # Check conflict resolution
        self.assertEqual(len(result.conflicts), 1)
        conflict = result.conflicts[0]
        self.assertEqual(conflict['resolution'], 'kept_remote')

    def test_import_conflict_keep_local(self):
        """Test conflict resolution keeps local when it has higher rate."""
        # Create import with same ID but lower helpful rate
        export_file = self._create_import_file([
            {
                "id": "exp001",  # Same ID as existing
                "problem_signature": "Unity XR element not found",
                "solution_approach": "Worse solution",
                "domain_context": {"project_type": "unity_xr"},
                "success_count": 1,
                "retrieval_count": 10,
                "helpful_count": 1,  # 10% vs existing 80%
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        result = self.manager.import_experiences(export_file)

        self.assertTrue(result.success)
        self.assertEqual(result.conflicts_resolved, 1)
        self.assertEqual(result.imported, 0)  # Not imported - kept local

        # Check conflict resolution
        conflict = result.conflicts[0]
        self.assertEqual(conflict['resolution'], 'kept_local')

    def test_import_dry_run(self):
        """Test import dry run doesn't modify data."""
        # Count experiences before
        before_count = len(self.manager._load_local_experiences())

        export_file = self._create_import_file([
            {
                "id": "new001",
                "problem_signature": "New problem",
                "solution_approach": "New solution",
                "domain_context": {"project_type": "ml_training"},
                "success_count": 5,
                "retrieval_count": 10,
                "helpful_count": 8,
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        result = self.manager.import_experiences(export_file, dry_run=True)

        # Count experiences after
        after_count = len(self.manager._load_local_experiences())

        self.assertTrue(result.success)
        self.assertEqual(result.imported, 1)
        self.assertEqual(before_count, after_count)  # No change

    def test_import_deduplication_similar(self):
        """Test deduplication of very similar experiences."""
        # Create an experience very similar to exp001
        export_file = self._create_import_file([
            {
                "id": "similar001",
                "problem_signature": "Unity XR element not found",  # Same as exp001
                "solution_approach": "Different solution",
                "domain_context": {"project_type": "unity_xr"},  # Same domain
                "success_count": 1,
                "retrieval_count": 5,
                "helpful_count": 1,  # 20% - lower than exp001's 80%
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        result = self.manager.import_experiences(export_file)

        self.assertTrue(result.success)
        self.assertEqual(result.skipped_duplicate, 1)  # Skipped as similar

    def test_import_file_not_found(self):
        """Test import with non-existent file."""
        result = self.manager.import_experiences("/nonexistent/file.jsonl.gz")

        self.assertFalse(result.success)
        self.assertIn("not found", result.error.lower())

    def test_audit_log_export(self):
        """Test audit log records exports."""
        self.manager.export_experiences()

        history = self.manager.get_sync_history(limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].operation, "export")
        self.assertTrue(history[0].success)

    def test_audit_log_import(self):
        """Test audit log records imports."""
        export_file = self._create_import_file([
            {
                "id": "new001",
                "problem_signature": "New problem",
                "solution_approach": "New solution",
                "domain_context": {"project_type": "ml_training"},
                "success_count": 5,
                "retrieval_count": 10,
                "helpful_count": 8,
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])

        self.manager.import_experiences(export_file)

        history = self.manager.get_sync_history(limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].operation, "import")
        self.assertTrue(history[0].success)

    def test_sync_stats(self):
        """Test sync statistics calculation."""
        # Do some operations
        self.manager.export_experiences()

        export_file = self._create_import_file([
            {
                "id": "new001",
                "problem_signature": "New problem",
                "solution_approach": "New solution",
                "domain_context": {"project_type": "ml_training"},
                "success_count": 5,
                "retrieval_count": 10,
                "helpful_count": 8,
                "last_used": "2026-01-12T00:00:00Z",
                "created_at": "2026-01-10T00:00:00Z",
            },
        ])
        self.manager.import_experiences(export_file)

        stats = self.manager.get_sync_stats()

        self.assertEqual(stats.total_exports, 1)
        self.assertEqual(stats.total_imports, 1)
        self.assertGreater(stats.total_experiences_exported, 0)
        self.assertIsNotNone(stats.last_export)
        self.assertIsNotNone(stats.last_import)

    def test_sync_folder_one_time(self):
        """Test one-time sync with folder."""
        sync_folder = os.path.join(self.test_dir, "shared")
        os.makedirs(sync_folder, exist_ok=True)

        result = self.manager.sync_folder(
            folder_path=sync_folder,
            watch=False,
            export_on_sync=True,
            import_existing=True,
        )

        self.assertIsNotNone(result.get('export_result'))
        self.assertTrue(result['export_result']['success'])

    def _create_import_file(self, experiences: list) -> str:
        """Create a temporary import file with given experiences."""
        import_dir = os.path.join(self.test_dir, "imports")
        os.makedirs(import_dir, exist_ok=True)

        import_file = os.path.join(import_dir, "test_import.jsonl.gz")
        content = "\n".join(json.dumps(exp) for exp in experiences)

        with gzip.open(import_file, 'wt', encoding='utf-8') as f:
            f.write(content)

        return import_file


class TestConflictDetail(unittest.TestCase):
    """Tests for ConflictDetail dataclass."""

    def test_conflict_detail_to_dict(self):
        """Test ConflictDetail serialization."""
        detail = ConflictDetail(
            experience_id="exp001",
            local_helpful_rate=0.8,
            remote_helpful_rate=0.6,
            resolution=ConflictResolution.KEPT_LOCAL,
        )

        data = detail.to_dict()
        self.assertEqual(data['experience_id'], "exp001")
        self.assertEqual(data['local_helpful_rate'], 0.8)
        self.assertEqual(data['resolution'], 'kept_local')


class TestSyncAuditEntry(unittest.TestCase):
    """Tests for SyncAuditEntry dataclass."""

    def test_audit_entry_to_dict(self):
        """Test SyncAuditEntry serialization."""
        entry = SyncAuditEntry(
            operation="export",
            timestamp="2026-01-12T00:00:00Z",
            path="/path/to/file",
            experience_count=10,
            domains=["unity_xr", "web_frontend"],
            duration_ms=100,
            success=True,
            details={"checksum": "abc123"},
        )

        data = entry.to_dict()
        self.assertEqual(data['operation'], "export")
        self.assertEqual(data['experience_count'], 10)
        self.assertEqual(len(data['domains']), 2)


class TestSyncStats(unittest.TestCase):
    """Tests for SyncStats dataclass."""

    def test_sync_stats_to_dict(self):
        """Test SyncStats serialization."""
        stats = SyncStats(
            total_exports=5,
            total_imports=3,
            total_experiences_exported=100,
            total_experiences_imported=50,
            total_conflicts_resolved=5,
            total_duplicates_skipped=10,
            last_export="2026-01-12T00:00:00Z",
            last_import="2026-01-11T00:00:00Z",
            domains_synced=["unity_xr", "web_frontend"],
        )

        data = stats.to_dict()
        self.assertEqual(data['total_exports'], 5)
        self.assertEqual(data['total_imports'], 3)
        self.assertEqual(len(data['domains_synced']), 2)


class TestMergeStrategy(unittest.TestCase):
    """Tests specifically for the merge strategy (keep higher helpful_rate)."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = ExperienceSyncManager(base_dir=self.test_dir)

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_higher_remote_rate_wins(self):
        """Test that higher helpful_rate from remote wins."""
        # Create local experience with 50% helpful rate
        self._create_local_experience(
            "exp001", helpful_count=5, retrieval_count=10
        )

        # Import experience with 80% helpful rate
        import_file = self._create_import_file(
            "exp001", helpful_count=8, retrieval_count=10
        )

        result = self.manager.import_experiences(import_file)

        self.assertEqual(result.conflicts[0]['resolution'], 'kept_remote')

    def test_higher_local_rate_wins(self):
        """Test that higher helpful_rate from local wins."""
        # Create local experience with 90% helpful rate
        self._create_local_experience(
            "exp001", helpful_count=9, retrieval_count=10
        )

        # Import experience with 30% helpful rate
        import_file = self._create_import_file(
            "exp001", helpful_count=3, retrieval_count=10
        )

        result = self.manager.import_experiences(import_file)

        self.assertEqual(result.conflicts[0]['resolution'], 'kept_local')

    def test_equal_rate_keeps_local(self):
        """Test that equal rates keep local version."""
        # Create local and remote with same rate
        self._create_local_experience(
            "exp001", helpful_count=5, retrieval_count=10  # 50%
        )

        import_file = self._create_import_file(
            "exp001", helpful_count=5, retrieval_count=10  # 50%
        )

        result = self.manager.import_experiences(import_file)

        self.assertEqual(result.conflicts[0]['resolution'], 'kept_local')

    def _create_local_experience(self, exp_id: str, helpful_count: int, retrieval_count: int):
        """Create a local experience."""
        experiences_dir = Path(self.test_dir) / ".claude-loop" / "experiences"
        experiences_dir.mkdir(parents=True, exist_ok=True)

        fallback_data = {
            "domains": {
                "other": {
                    "experiences": {
                        exp_id: {
                            "problem_signature": "Test problem",
                            "solution_approach": "Test solution",
                            "domain_context": {"project_type": "other"},
                            "success_count": 1,
                            "retrieval_count": retrieval_count,
                            "helpful_count": helpful_count,
                            "last_used": "2026-01-12T00:00:00Z",
                            "created_at": "2026-01-10T00:00:00Z",
                        },
                    },
                    "embeddings": {},
                },
            }
        }

        with open(experiences_dir / "experiences_fallback.json", 'w') as f:
            json.dump(fallback_data, f)

    def _create_import_file(self, exp_id: str, helpful_count: int, retrieval_count: int) -> str:
        """Create an import file with specified experience."""
        import_dir = os.path.join(self.test_dir, "imports")
        os.makedirs(import_dir, exist_ok=True)

        import_file = os.path.join(import_dir, "test_import.jsonl.gz")
        exp = {
            "id": exp_id,
            "problem_signature": "Test problem",
            "solution_approach": "Test solution",
            "domain_context": {"project_type": "other"},
            "success_count": 1,
            "retrieval_count": retrieval_count,
            "helpful_count": helpful_count,
            "last_used": "2026-01-12T00:00:00Z",
            "created_at": "2026-01-10T00:00:00Z",
        }

        with gzip.open(import_file, 'wt', encoding='utf-8') as f:
            f.write(json.dumps(exp))

        return import_file


if __name__ == '__main__':
    unittest.main()
