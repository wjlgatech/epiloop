#!/usr/bin/env python3
"""
test_retention.py - Tests for PRD Retention Policy Automation

Tests the retention policy functionality from prd-retention.py:
- Scanning for retention actions
- Auto-abandon of stale drafts
- Archiving completed PRDs
- Deleting old abandoned PRDs
- Compressing archives

Usage:
    pytest tests/test_retention.py -v
    pytest tests/test_retention.py::TestRetentionActions -v
"""

import json
import sys
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

# Add lib to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import prd-retention module
import importlib.util
spec = importlib.util.spec_from_file_location("prd_retention", lib_path / "prd-retention.py")
if spec and spec.loader:
    sys.modules["prd_retention"] = importlib.util.module_from_spec(spec)
    prd_retention = sys.modules["prd_retention"]
    spec.loader.exec_module(prd_retention)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_prds_dir(tmp_path):
    """Create a temporary PRDs directory structure."""
    prds_dir = tmp_path / "prds"

    # Create status subdirectories
    for subdir in ['active', 'completed', 'abandoned', 'drafts', 'archive']:
        (prds_dir / subdir).mkdir(parents=True)

    # Create .claude-loop directory
    claude_loop_dir = tmp_path / ".claude-loop"
    claude_loop_dir.mkdir(parents=True)

    return prds_dir


def create_prd_with_age(prds_dir, status, prd_id, title, age_days, status_date_field='created_at'):
    """Helper to create a PRD with a specific age."""
    import yaml

    status_dir_map = {
        'draft': 'drafts',
        'active': 'active',
        'completed': 'completed',
        'abandoned': 'abandoned'
    }

    prd_dir = prds_dir / status_dir_map[status] / prd_id.lower().replace('-', '')
    prd_dir.mkdir(parents=True, exist_ok=True)

    # Calculate timestamps
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=age_days)
    old_timestamp = old_date.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Create prd.json
    prd_json = {
        "project": prd_id.lower(),
        "branchName": f"feature/{prd_id.lower()}",
        "description": f"Test PRD {title}",
        "userStories": [
            {
                "id": f"{prd_id}-001",
                "title": "Test Story",
                "description": "Test",
                "acceptanceCriteria": ["Test"],
                "priority": 1,
                "passes": status == 'completed',
                "notes": ""
            }
        ]
    }
    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Create MANIFEST.yaml
    manifest = {
        "id": prd_id,
        "title": title,
        "status": status,
        "owner": "retention-test",
        "created_at": old_timestamp,
        "updated_at": old_timestamp,
    }

    # Add status-specific fields
    if status == 'completed':
        manifest['completed_at'] = old_timestamp
    elif status == 'abandoned':
        manifest['abandoned_at'] = old_timestamp
        manifest['abandon_reason'] = "Test abandonment"

    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    # Set file mtime to match age
    import os
    old_mtime = old_date.timestamp()
    for file in prd_dir.iterdir():
        os.utime(file, (old_mtime, old_mtime))

    return prd_dir


@pytest.fixture
def patched_paths(temp_prds_dir, monkeypatch):
    """Patch module paths to use temporary directories."""
    project_root = temp_prds_dir.parent
    monkeypatch.setattr(prd_retention, 'PRDS_DIR', temp_prds_dir)
    monkeypatch.setattr(prd_retention, 'PROJECT_ROOT', project_root)
    monkeypatch.setattr(prd_retention, 'ARCHIVE_DIR', temp_prds_dir / "archive")
    monkeypatch.setattr(prd_retention, 'CLAUDE_LOOP_DIR', project_root / ".claude-loop")
    monkeypatch.setattr(prd_retention, 'AUDIT_LOG_FILE', project_root / ".claude-loop" / "audit-log.jsonl")
    return temp_prds_dir


# ============================================================================
# Test: Retention Configuration
# ============================================================================


class TestRetentionConfig:
    """Tests for retention configuration."""

    def test_config_has_required_keys(self):
        """Test that config has all required keys."""
        required_keys = [
            'draft_warning_days',
            'draft_abandon_days',
            'completed_archive_days',
            'abandoned_delete_days',
            'archive_compress_days'
        ]

        for key in required_keys:
            assert key in prd_retention.RETENTION_CONFIG, f"Missing config key: {key}"

    def test_config_values_are_positive(self):
        """Test that all config values are positive integers."""
        for key, value in prd_retention.RETENTION_CONFIG.items():
            assert isinstance(value, int), f"{key} should be int"
            assert value > 0, f"{key} should be positive"

    def test_warning_before_abandon(self):
        """Test that warning threshold is less than abandon threshold."""
        assert prd_retention.RETENTION_CONFIG['draft_warning_days'] < \
               prd_retention.RETENTION_CONFIG['draft_abandon_days']


# ============================================================================
# Test: Retention Action Dataclass
# ============================================================================


class TestRetentionAction:
    """Tests for RetentionAction dataclass."""

    def test_create_retention_action(self):
        """Test creating a RetentionAction."""
        action = prd_retention.RetentionAction(
            action_type='abandon',
            prd_id='TEST-001',
            prd_path='/test/path',
            reason='Test reason',
            age_days=35,
            threshold_days=30
        )

        assert action.action_type == 'abandon'
        assert action.prd_id == 'TEST-001'
        assert action.age_days == 35
        assert action.details == {}

    def test_retention_action_with_details(self):
        """Test RetentionAction with details."""
        action = prd_retention.RetentionAction(
            action_type='warn',
            prd_id='TEST-002',
            prd_path='/test/path',
            reason='Warning',
            age_days=26,
            threshold_days=25,
            details={'days_until_abandon': 4}
        )

        assert action.details['days_until_abandon'] == 4


# ============================================================================
# Test: Retention Stats Dataclass
# ============================================================================


class TestRetentionStats:
    """Tests for RetentionStats dataclass."""

    def test_retention_stats_defaults(self):
        """Test RetentionStats default values."""
        stats = prd_retention.RetentionStats()

        assert stats.total_prds == 0
        assert stats.drafts == 0
        assert stats.active == 0
        assert stats.completed == 0
        assert stats.abandoned == 0
        assert stats.archived == 0
        assert stats.pending_actions == 0


# ============================================================================
# Test: Scan for Retention Actions
# ============================================================================


class TestScanRetentionActions:
    """Tests for scanning and detecting retention actions."""

    def test_scan_empty_directory(self, temp_prds_dir, patched_paths):
        """Test scanning empty PRDs directory."""
        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        assert len(actions) == 0
        assert stats.total_prds == 0

    def test_scan_detects_warning(self, temp_prds_dir, patched_paths):
        """Test that scan detects draft warnings."""
        import yaml
        # Create draft PRD aged 26 days (warning at 25)
        create_prd_with_age(temp_prds_dir, 'draft', 'WARN-001', 'Warning Test', 26)

        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        warnings = [a for a in actions if a.action_type == 'warn']
        assert len(warnings) == 1
        assert warnings[0].prd_id == 'WARN-001'

    def test_scan_detects_abandon(self, temp_prds_dir, patched_paths):
        """Test that scan detects drafts to abandon."""
        import yaml
        # Create draft PRD aged 35 days (abandon at 30)
        create_prd_with_age(temp_prds_dir, 'draft', 'ABAND-001', 'Abandon Test', 35)

        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        abandons = [a for a in actions if a.action_type == 'abandon']
        assert len(abandons) == 1
        assert abandons[0].prd_id == 'ABAND-001'

    def test_scan_detects_archive(self, temp_prds_dir, patched_paths):
        """Test that scan detects completed PRDs to archive."""
        import yaml
        # Create completed PRD aged 100 days (archive at 90)
        create_prd_with_age(temp_prds_dir, 'completed', 'ARCH-001', 'Archive Test', 100)

        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        archives = [a for a in actions if a.action_type == 'archive']
        assert len(archives) == 1
        assert archives[0].prd_id == 'ARCH-001'

    def test_scan_detects_delete(self, temp_prds_dir, patched_paths):
        """Test that scan detects abandoned PRDs to delete."""
        import yaml
        # Create abandoned PRD aged 40 days (delete at 30)
        create_prd_with_age(temp_prds_dir, 'abandoned', 'DEL-001', 'Delete Test', 40)

        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        deletes = [a for a in actions if a.action_type == 'delete']
        assert len(deletes) == 1
        assert deletes[0].prd_id == 'DEL-001'

    def test_scan_stats_counts(self, temp_prds_dir, patched_paths):
        """Test that scan returns correct stats counts."""
        import yaml
        # Create PRDs in different statuses
        create_prd_with_age(temp_prds_dir, 'draft', 'D1', 'Draft 1', 5)
        create_prd_with_age(temp_prds_dir, 'draft', 'D2', 'Draft 2', 10)
        create_prd_with_age(temp_prds_dir, 'active', 'A1', 'Active 1', 15)
        create_prd_with_age(temp_prds_dir, 'completed', 'C1', 'Completed 1', 30)
        create_prd_with_age(temp_prds_dir, 'abandoned', 'AB1', 'Abandoned 1', 10)

        actions, stats = prd_retention.scan_for_retention_actions(temp_prds_dir)

        assert stats.total_prds == 5
        assert stats.drafts == 2
        assert stats.active == 1
        assert stats.completed == 1
        assert stats.abandoned == 1


# ============================================================================
# Test: Execute Abandon Action
# ============================================================================


class TestExecuteAbandonAction:
    """Tests for executing abandon actions on stale drafts."""

    def test_abandon_dry_run(self, temp_prds_dir, patched_paths):
        """Test abandon action in dry run mode."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'draft', 'DRY-001', 'Dry Run', 35)

        action = prd_retention.RetentionAction(
            action_type='abandon',
            prd_id='DRY-001',
            prd_path=str(prd_dir),
            reason='Stale draft',
            age_days=35,
            threshold_days=30
        )

        success, message = prd_retention.execute_abandon_action(action, dry_run=True)

        assert success is True
        assert "Would abandon" in message

        # PRD should still be in drafts
        assert prd_dir.exists()

    def test_abandon_actual(self, temp_prds_dir, patched_paths):
        """Test actually abandoning a stale draft."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'draft', 'ACT-001', 'Actual Abandon', 35)

        action = prd_retention.RetentionAction(
            action_type='abandon',
            prd_id='ACT-001',
            prd_path=str(prd_dir),
            reason='Stale draft',
            age_days=35,
            threshold_days=30
        )

        success, message = prd_retention.execute_abandon_action(action, dry_run=False)

        assert success is True

        # PRD should have moved to abandoned
        assert not prd_dir.exists()
        abandoned_dir = temp_prds_dir / "abandoned" / prd_dir.name
        assert abandoned_dir.exists()

        # MANIFEST should have status=abandoned
        with open(abandoned_dir / "MANIFEST.yaml") as f:
            manifest = yaml.safe_load(f)
        assert manifest['status'] == 'abandoned'
        assert 'retention policy' in manifest.get('abandon_reason', '').lower()


# ============================================================================
# Test: Execute Archive Action
# ============================================================================


class TestExecuteArchiveAction:
    """Tests for executing archive actions on completed PRDs."""

    def test_archive_dry_run(self, temp_prds_dir, patched_paths):
        """Test archive action in dry run mode."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'completed', 'ARCHDRY-001', 'Archive Dry', 100)

        action = prd_retention.RetentionAction(
            action_type='archive',
            prd_id='ARCHDRY-001',
            prd_path=str(prd_dir),
            reason='Old completed',
            age_days=100,
            threshold_days=90
        )

        success, message = prd_retention.execute_archive_action(action, dry_run=True)

        assert success is True
        assert "Would archive" in message

        # PRD should still be in completed
        assert prd_dir.exists()

    def test_archive_actual(self, temp_prds_dir, patched_paths):
        """Test actually archiving a completed PRD."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'completed', 'ARCHACT-001', 'Archive Actual', 100)

        action = prd_retention.RetentionAction(
            action_type='archive',
            prd_id='ARCHACT-001',
            prd_path=str(prd_dir),
            reason='Old completed',
            age_days=100,
            threshold_days=90
        )

        success, message = prd_retention.execute_archive_action(action, dry_run=False)

        assert success is True

        # PRD should have moved to archive
        assert not prd_dir.exists()
        archive_dir = temp_prds_dir / "archive" / prd_dir.name
        assert archive_dir.exists()


# ============================================================================
# Test: Execute Delete Action
# ============================================================================


class TestExecuteDeleteAction:
    """Tests for executing delete actions on old abandoned PRDs."""

    def test_delete_dry_run(self, temp_prds_dir, patched_paths):
        """Test delete action in dry run mode."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'abandoned', 'DELDRY-001', 'Delete Dry', 40)

        action = prd_retention.RetentionAction(
            action_type='delete',
            prd_id='DELDRY-001',
            prd_path=str(prd_dir),
            reason='Old abandoned',
            age_days=40,
            threshold_days=30
        )

        success, message = prd_retention.execute_delete_action(action, dry_run=True)

        assert success is True
        assert "Would delete" in message

        # PRD should still exist
        assert prd_dir.exists()

    def test_delete_actual(self, temp_prds_dir, patched_paths):
        """Test actually deleting an old abandoned PRD."""
        import yaml
        prd_dir = create_prd_with_age(temp_prds_dir, 'abandoned', 'DELACT-001', 'Delete Actual', 40)

        action = prd_retention.RetentionAction(
            action_type='delete',
            prd_id='DELACT-001',
            prd_path=str(prd_dir),
            reason='Old abandoned',
            age_days=40,
            threshold_days=30,
            details={'abandon_reason': 'Test'}
        )

        success, message = prd_retention.execute_delete_action(action, dry_run=False)

        assert success is True

        # PRD should be deleted
        assert not prd_dir.exists()

        # Audit entry should be preserved
        # (audit log is created during execution)


# ============================================================================
# Test: Execute Compress Action
# ============================================================================


class TestExecuteCompressAction:
    """Tests for executing compress actions on archives."""

    def test_compress_dry_run(self, temp_prds_dir, patched_paths):
        """Test compress action in dry run mode."""
        # Create archive directory
        archive_dir = temp_prds_dir / "archive" / "compress-dry"
        archive_dir.mkdir(parents=True)
        (archive_dir / "test.txt").write_text("test content")

        action = prd_retention.RetentionAction(
            action_type='compress',
            prd_id='compress-dry',
            prd_path=str(archive_dir),
            reason='Old archive',
            age_days=10,
            threshold_days=7
        )

        success, message = prd_retention.execute_compress_action(action, dry_run=True)

        assert success is True
        assert "Would compress" in message

        # Directory should still exist (not compressed)
        assert archive_dir.exists()
        assert not archive_dir.with_suffix('.tar.gz').exists()

    def test_compress_actual(self, temp_prds_dir, patched_paths):
        """Test actually compressing an archive."""
        # Create archive directory
        archive_dir = temp_prds_dir / "archive" / "compress-actual"
        archive_dir.mkdir(parents=True)
        (archive_dir / "test.txt").write_text("test content for compression")

        action = prd_retention.RetentionAction(
            action_type='compress',
            prd_id='compress-actual',
            prd_path=str(archive_dir),
            reason='Old archive',
            age_days=10,
            threshold_days=7
        )

        success, message = prd_retention.execute_compress_action(action, dry_run=False)

        assert success is True

        # Directory should be replaced with tar.gz
        assert not archive_dir.exists()
        tar_path = archive_dir.with_suffix('.tar.gz')
        assert tar_path.exists()

        # Verify tar contains the original content
        with tarfile.open(tar_path, 'r:gz') as tar:
            names = tar.getnames()
            assert any('test.txt' in name for name in names)


# ============================================================================
# Test: Execute Retention Actions
# ============================================================================


class TestExecuteRetentionActions:
    """Tests for executing multiple retention actions."""

    def test_execute_multiple_actions(self, temp_prds_dir, patched_paths):
        """Test executing multiple actions."""
        import yaml

        # Create PRDs that need action
        create_prd_with_age(temp_prds_dir, 'draft', 'MULTI-001', 'Stale Draft', 35)
        create_prd_with_age(temp_prds_dir, 'abandoned', 'MULTI-002', 'Old Abandoned', 40)

        actions, _ = prd_retention.scan_for_retention_actions(temp_prds_dir)

        # Filter to non-warning actions
        executable = [a for a in actions if a.action_type != 'warn']

        success_count, failure_count, results = prd_retention.execute_retention_actions(
            executable, dry_run=True
        )

        assert len(results) == len(executable)
        assert failure_count == 0

    def test_execute_skips_warnings(self, temp_prds_dir, patched_paths):
        """Test that execution skips warning actions."""
        import yaml

        # Create draft at warning threshold (26 days)
        create_prd_with_age(temp_prds_dir, 'draft', 'SKIPWARN-001', 'Warning Only', 26)

        actions, _ = prd_retention.scan_for_retention_actions(temp_prds_dir)

        success_count, failure_count, results = prd_retention.execute_retention_actions(
            actions, dry_run=False
        )

        # Warning should be in results but not executed
        warning_results = [r for r in results if r['action'] == 'warn']
        assert len(warning_results) == 1
        assert warning_results[0]['success'] is True  # Warning is always "successful"


# ============================================================================
# Test: Timestamp Parsing
# ============================================================================


class TestTimestampParsing:
    """Tests for timestamp parsing utilities."""

    def test_parse_iso_timestamp(self):
        """Test parsing ISO 8601 timestamp."""
        result = prd_retention.parse_timestamp("2026-01-01T12:30:00Z")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 1

    def test_parse_date_only(self):
        """Test parsing date-only format."""
        result = prd_retention.parse_timestamp("2026-01-15")

        assert result is not None
        assert result.year == 2026
        assert result.day == 15

    def test_parse_invalid_timestamp(self):
        """Test parsing invalid timestamp returns None."""
        result = prd_retention.parse_timestamp("not-a-date")
        assert result is None

    def test_parse_empty_timestamp(self):
        """Test parsing empty timestamp returns None."""
        result = prd_retention.parse_timestamp("")
        assert result is None


# ============================================================================
# Test: Days Since Calculation
# ============================================================================


class TestDaysSince:
    """Tests for days_since calculation."""

    def test_days_since_recent(self):
        """Test days since a recent date."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=5)

        days = prd_retention.days_since(recent)

        assert days == 5

    def test_days_since_old(self):
        """Test days since an old date."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=100)

        days = prd_retention.days_since(old)

        assert days == 100


# ============================================================================
# Test: Get PRD Last Activity
# ============================================================================


class TestGetPRDLastActivity:
    """Tests for determining PRD last activity date."""

    def test_last_activity_from_updated_at(self, temp_prds_dir, patched_paths):
        """Test getting last activity from updated_at."""
        import yaml

        prd_dir = create_prd_with_age(temp_prds_dir, 'draft', 'LAST-001', 'Last Activity', 10)

        manifest = {
            "id": "LAST-001",
            "status": "draft",
            "owner": "test",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2026-01-05T00:00:00Z"  # More recent
        }

        result = prd_retention.get_prd_last_activity(prd_dir, manifest)

        assert result is not None
        # Should use the most recent date
        assert result.year == 2026

    def test_last_activity_considers_file_mtime(self, temp_prds_dir, patched_paths):
        """Test that file mtime is considered for last activity."""
        import yaml
        import os

        prd_dir = temp_prds_dir / "drafts" / "mtime-test"
        prd_dir.mkdir(parents=True)

        # Create files
        prd_json = {"project": "test", "userStories": []}
        with open(prd_dir / "prd.json", 'w') as f:
            json.dump(prd_json, f)

        manifest = {
            "id": "MTIME-001",
            "status": "draft",
            "created_at": "2020-01-01T00:00:00Z"  # Very old
        }
        with open(prd_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        result = prd_retention.get_prd_last_activity(prd_dir, manifest)

        # Should use file mtime which is recent (just created)
        assert result is not None
        now = datetime.now(timezone.utc)
        assert (now - result).days < 1  # Within last day
