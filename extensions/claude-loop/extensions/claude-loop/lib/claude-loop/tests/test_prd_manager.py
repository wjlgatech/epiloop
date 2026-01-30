#!/usr/bin/env python3
"""
test_prd_manager.py - Tests for PRD Manager CLI

Tests the core and lifecycle commands of prd-manager.py:
- list, show, search commands
- create, approve, abandon, complete lifecycle commands
- verify command for integrity checking
- audit command for log viewing

Usage:
    pytest tests/test_prd_manager.py -v
    pytest tests/test_prd_manager.py::TestListCommand -v
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest

# Add lib to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import prd-manager module
import importlib.util
spec = importlib.util.spec_from_file_location("prd_manager", lib_path / "prd-manager.py")
sys.modules["prd_manager"] = importlib.util.module_from_spec(spec)
prd_manager = sys.modules["prd_manager"]
spec.loader.exec_module(prd_manager)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_prds_dir(tmp_path):
    """Create a temporary PRDs directory structure."""
    prds_dir = tmp_path / "prds"

    # Create status subdirectories
    for subdir in ['active', 'completed', 'abandoned', 'drafts']:
        (prds_dir / subdir).mkdir(parents=True)

    # Create .claude-loop directory
    claude_loop_dir = tmp_path / ".claude-loop"
    claude_loop_dir.mkdir(parents=True)

    return prds_dir


@pytest.fixture
def sample_prd_draft(temp_prds_dir):
    """Create a sample draft PRD."""
    prd_dir = temp_prds_dir / "drafts" / "test-feature"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "test-feature",
        "branchName": "feature/test-001",
        "description": "A test feature PRD",
        "userStories": [
            {
                "id": "TEST-001",
                "title": "First Story",
                "description": "Implement feature X",
                "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
                "priority": 1,
                "passes": False,
                "notes": ""
            },
            {
                "id": "TEST-002",
                "title": "Second Story",
                "description": "Implement feature Y",
                "acceptanceCriteria": ["Criterion 3"],
                "priority": 2,
                "passes": False,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Create MANIFEST.yaml
    manifest = {
        "id": "TEST-001",
        "title": "Test Feature",
        "status": "draft",
        "owner": "test-user",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "tags": ["test", "feature"],
        "priority": "medium",
        "description": "A test feature PRD",
        "story_count": 2,
        "completed_stories": 0,
        "branch_name": "feature/test-001"
    }

    import yaml
    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    return prd_dir


@pytest.fixture
def sample_prd_active(temp_prds_dir):
    """Create a sample active PRD."""
    prd_dir = temp_prds_dir / "active" / "active-feature"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "active-feature",
        "branchName": "feature/active-001",
        "description": "An active feature PRD",
        "userStories": [
            {
                "id": "ACT-001",
                "title": "Active Story",
                "description": "Implement active feature",
                "acceptanceCriteria": ["Criterion 1"],
                "priority": 1,
                "passes": True,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Compute hash for approval
    import hashlib
    with open(prd_dir / "prd.json", 'rb') as f:
        prd_hash = hashlib.sha256(f.read()).hexdigest()

    # Create MANIFEST.yaml
    manifest = {
        "id": "ACT-001",
        "title": "Active Feature",
        "status": "active",
        "owner": "test-user",
        "created_at": "2026-01-01T00:00:00Z",
        "approved_at": "2026-01-02T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "tags": ["active"],
        "priority": "high",
        "description": "An active feature PRD",
        "story_count": 1,
        "completed_stories": 1,
        "branch_name": "feature/active-001",
        "approval": {
            "approved_by": "approver",
            "approved_at": "2026-01-02T00:00:00Z",
            "approval_hash": prd_hash
        }
    }

    import yaml
    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    return prd_dir


@pytest.fixture
def sample_prd_completed(temp_prds_dir):
    """Create a sample completed PRD."""
    prd_dir = temp_prds_dir / "completed" / "completed-feature"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "completed-feature",
        "branchName": "feature/comp-001",
        "description": "A completed feature PRD",
        "userStories": [
            {
                "id": "COMP-001",
                "title": "Completed Story",
                "description": "Completed feature",
                "acceptanceCriteria": ["Done"],
                "priority": 1,
                "passes": True,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Compute hash for approval
    import hashlib
    with open(prd_dir / "prd.json", 'rb') as f:
        prd_hash = hashlib.sha256(f.read()).hexdigest()

    # Create MANIFEST.yaml
    manifest = {
        "id": "COMP-001",
        "title": "Completed Feature",
        "status": "completed",
        "owner": "test-user",
        "created_at": "2025-12-01T00:00:00Z",
        "approved_at": "2025-12-02T00:00:00Z",
        "completed_at": "2025-12-15T00:00:00Z",
        "updated_at": "2025-12-15T00:00:00Z",
        "tags": ["completed"],
        "priority": "low",
        "description": "A completed feature PRD",
        "story_count": 1,
        "completed_stories": 1,
        "branch_name": "feature/comp-001",
        "approval": {
            "approved_by": "approver",
            "approved_at": "2025-12-02T00:00:00Z",
            "approval_hash": prd_hash
        }
    }

    import yaml
    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    return prd_dir


@pytest.fixture
def patched_paths(temp_prds_dir, monkeypatch):
    """Patch module paths to use temporary directories."""
    project_root = temp_prds_dir.parent
    monkeypatch.setattr(prd_manager, 'PRDS_DIR', temp_prds_dir)
    monkeypatch.setattr(prd_manager, 'PROJECT_ROOT', project_root)
    monkeypatch.setattr(prd_manager, 'CLAUDE_LOOP_DIR', project_root / ".claude-loop")
    monkeypatch.setattr(prd_manager, 'AUDIT_LOG_FILE', project_root / ".claude-loop" / "audit-log.jsonl")
    monkeypatch.setattr(prd_manager, 'INDEX_FILE', project_root / ".claude-loop" / "prd-index.json")
    return temp_prds_dir


# ============================================================================
# Test: PRD Info Extraction
# ============================================================================


class TestPRDInfoExtraction:
    """Tests for PRD info extraction from directories."""

    def test_get_prd_info_draft(self, sample_prd_draft, patched_paths):
        """Test extracting info from a draft PRD."""
        info = prd_manager.get_prd_info(sample_prd_draft)

        assert info is not None
        assert info.id == "TEST-001"
        assert info.title == "Test Feature"
        assert info.status == "draft"
        assert info.owner == "test-user"
        assert info.story_count == 2
        assert info.completed_stories == 0
        assert "test" in info.tags
        assert "feature" in info.tags

    def test_get_prd_info_active(self, sample_prd_active, patched_paths):
        """Test extracting info from an active PRD."""
        info = prd_manager.get_prd_info(sample_prd_active)

        assert info is not None
        assert info.id == "ACT-001"
        assert info.status == "active"
        assert info.story_count == 1
        assert info.completed_stories == 1

    def test_get_prd_info_missing_manifest(self, temp_prds_dir, patched_paths):
        """Test that missing manifest returns None."""
        empty_dir = temp_prds_dir / "drafts" / "no-manifest"
        empty_dir.mkdir(parents=True)

        info = prd_manager.get_prd_info(empty_dir)
        assert info is None


# ============================================================================
# Test: Scan PRDs
# ============================================================================


class TestScanPRDs:
    """Tests for scanning PRDs directory."""

    def test_scan_empty_directory(self, temp_prds_dir, patched_paths):
        """Test scanning empty PRDs directory."""
        prds = prd_manager.scan_prds(temp_prds_dir)
        assert len(prds) == 0

    def test_scan_with_prds(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test scanning directory with PRDs."""
        prds = prd_manager.scan_prds(temp_prds_dir)

        assert len(prds) == 2

        # Check we have both PRDs
        ids = {p.id for p in prds}
        assert "TEST-001" in ids
        assert "ACT-001" in ids

    def test_scan_with_status_filter(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test scanning with status filter."""
        draft_prds = prd_manager.scan_prds(temp_prds_dir, status_filter='draft')
        assert len(draft_prds) == 1
        assert draft_prds[0].id == "TEST-001"

        active_prds = prd_manager.scan_prds(temp_prds_dir, status_filter='active')
        assert len(active_prds) == 1
        assert active_prds[0].id == "ACT-001"


# ============================================================================
# Test: Search PRDs
# ============================================================================


class TestSearchPRDs:
    """Tests for PRD search functionality."""

    def test_search_by_keyword(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test searching PRDs by keyword."""
        # Search for 'test' should find draft PRD
        results = prd_manager.search_prds(temp_prds_dir, "test")
        assert len(results) >= 1
        assert any(p.id == "TEST-001" for p in results)

    def test_search_by_tag(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test searching PRDs by tag."""
        results = prd_manager.search_prds(temp_prds_dir, "", tag="feature")
        assert len(results) == 1
        assert results[0].id == "TEST-001"

    def test_search_no_results(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test search with no results."""
        results = prd_manager.search_prds(temp_prds_dir, "nonexistent-query-12345")
        assert len(results) == 0


# ============================================================================
# Test: Find PRD by ID or Path
# ============================================================================


class TestFindPRD:
    """Tests for finding PRD by ID or path."""

    def test_find_by_id(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test finding PRD by ID."""
        result = prd_manager.find_prd_by_id_or_path("TEST-001", temp_prds_dir)

        assert result is not None
        prd_info, prd_path = result
        assert prd_info.id == "TEST-001"

    def test_find_by_partial_id(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test finding PRD by partial ID."""
        result = prd_manager.find_prd_by_id_or_path("TEST", temp_prds_dir)

        assert result is not None
        prd_info, prd_path = result
        assert prd_info.id == "TEST-001"

    def test_find_by_path(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test finding PRD by path."""
        result = prd_manager.find_prd_by_id_or_path(str(sample_prd_draft), temp_prds_dir)

        assert result is not None
        prd_info, prd_path = result
        assert prd_info.id == "TEST-001"

    def test_find_nonexistent(self, temp_prds_dir, patched_paths):
        """Test finding nonexistent PRD."""
        result = prd_manager.find_prd_by_id_or_path("NONEXISTENT-999", temp_prds_dir)
        assert result is None


# ============================================================================
# Test: State Transitions
# ============================================================================


class TestStateTransitions:
    """Tests for PRD state transition validation."""

    def test_valid_draft_to_active(self):
        """Test valid transition from draft to active."""
        valid, msg = prd_manager.validate_state_transition('draft', 'active')
        assert valid is True

    def test_valid_draft_to_abandoned(self):
        """Test valid transition from draft to abandoned."""
        valid, msg = prd_manager.validate_state_transition('draft', 'abandoned')
        assert valid is True

    def test_valid_active_to_completed(self):
        """Test valid transition from active to completed."""
        valid, msg = prd_manager.validate_state_transition('active', 'completed')
        assert valid is True

    def test_valid_active_to_abandoned(self):
        """Test valid transition from active to abandoned."""
        valid, msg = prd_manager.validate_state_transition('active', 'abandoned')
        assert valid is True

    def test_invalid_completed_transition(self):
        """Test that completed is a terminal state."""
        valid, msg = prd_manager.validate_state_transition('completed', 'active')
        assert valid is False
        assert "terminal" in msg.lower()

    def test_invalid_abandoned_transition(self):
        """Test that abandoned is a terminal state."""
        valid, msg = prd_manager.validate_state_transition('abandoned', 'draft')
        assert valid is False
        assert "terminal" in msg.lower()

    def test_invalid_draft_to_completed(self):
        """Test invalid transition from draft directly to completed."""
        valid, msg = prd_manager.validate_state_transition('draft', 'completed')
        assert valid is False


# ============================================================================
# Test: Hash Computation
# ============================================================================


class TestHashComputation:
    """Tests for hash computation functions."""

    def test_compute_prd_hash(self, sample_prd_draft):
        """Test computing hash of prd.json."""
        prd_json_path = sample_prd_draft / "prd.json"
        hash_value = prd_manager.compute_prd_hash(prd_json_path)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hex length

    def test_compute_content_hash(self, sample_prd_draft):
        """Test computing combined content hash."""
        hash_value = prd_manager.compute_content_hash(sample_prd_draft)

        assert hash_value is not None
        assert len(hash_value) == 64


# ============================================================================
# Test: Manifest Operations
# ============================================================================


class TestManifestOperations:
    """Tests for manifest load/save operations."""

    def test_load_manifest(self, sample_prd_draft):
        """Test loading MANIFEST.yaml."""
        manifest_path = sample_prd_draft / "MANIFEST.yaml"
        manifest = prd_manager.load_manifest(manifest_path)

        assert manifest is not None
        assert manifest['id'] == "TEST-001"
        assert manifest['status'] == "draft"

    def test_save_manifest(self, temp_prds_dir):
        """Test saving MANIFEST.yaml."""
        test_dir = temp_prds_dir / "drafts" / "save-test"
        test_dir.mkdir(parents=True)

        manifest = {
            "id": "SAVE-001",
            "title": "Save Test",
            "status": "draft",
            "owner": "tester"
        }

        manifest_path = test_dir / "MANIFEST.yaml"
        result = prd_manager.save_manifest(manifest_path, manifest)

        assert result is True
        assert manifest_path.exists()

        # Verify content
        loaded = prd_manager.load_manifest(manifest_path)
        assert loaded['id'] == "SAVE-001"


# ============================================================================
# Test: Integrity Verification
# ============================================================================


class TestIntegrityVerification:
    """Tests for PRD integrity verification."""

    def test_verify_active_prd_valid(self, sample_prd_active, patched_paths):
        """Test verifying a valid active PRD."""
        issues = prd_manager.verify_prd_integrity(sample_prd_active)
        assert len(issues) == 0

    def test_verify_draft_prd(self, sample_prd_draft, patched_paths):
        """Test verifying a draft PRD (no approval hash required)."""
        issues = prd_manager.verify_prd_integrity(sample_prd_draft)
        # Draft PRDs don't need approval hashes
        hash_issues = [i for i in issues if i.issue_type == 'hash_mismatch']
        assert len(hash_issues) == 0

    def test_verify_missing_manifest(self, temp_prds_dir, patched_paths):
        """Test verification with missing manifest."""
        empty_dir = temp_prds_dir / "active" / "no-manifest"
        empty_dir.mkdir(parents=True)

        issues = prd_manager.verify_prd_integrity(empty_dir)
        assert len(issues) == 1
        assert issues[0].issue_type == 'missing_manifest'

    def test_verify_hash_mismatch(self, sample_prd_active, patched_paths):
        """Test detection of hash mismatch."""
        # Modify prd.json after approval
        prd_json_path = sample_prd_active / "prd.json"
        with open(prd_json_path, 'r') as f:
            data = json.load(f)

        data['description'] = "Modified description"

        with open(prd_json_path, 'w') as f:
            json.dump(data, f)

        issues = prd_manager.verify_prd_integrity(sample_prd_active)

        hash_issues = [i for i in issues if i.issue_type == 'hash_mismatch']
        assert len(hash_issues) == 1


# ============================================================================
# Test: Audit Log
# ============================================================================


class TestAuditLog:
    """Tests for audit log functionality."""

    def test_log_audit_entry(self, sample_prd_draft, patched_paths):
        """Test logging an audit entry."""
        result = prd_manager.log_audit_entry(
            action="test_action",
            prd_id="TEST-001",
            prd_dir=sample_prd_draft,
            actor="test-user",
            details={"test_key": "test_value"}
        )

        assert result is True
        assert prd_manager.AUDIT_LOG_FILE.exists()

    def test_read_audit_log(self, sample_prd_draft, patched_paths):
        """Test reading audit log entries."""
        # Log an entry first
        prd_manager.log_audit_entry(
            action="test_read",
            prd_id="TEST-001",
            prd_dir=sample_prd_draft,
            actor="reader"
        )

        entries = prd_manager.read_audit_log()
        assert len(entries) >= 1
        assert entries[0]['action'] == "test_read"

    def test_read_audit_log_filtered(self, sample_prd_draft, patched_paths):
        """Test reading audit log with filters."""
        # Log multiple entries
        prd_manager.log_audit_entry(
            action="create",
            prd_id="TEST-001",
            prd_dir=sample_prd_draft
        )
        prd_manager.log_audit_entry(
            action="approve",
            prd_id="TEST-002",
            prd_dir=sample_prd_draft
        )

        # Filter by action
        create_entries = prd_manager.read_audit_log(action="create")
        assert all(e['action'] == 'create' for e in create_entries)

        # Filter by PRD ID
        test001_entries = prd_manager.read_audit_log(prd_id="TEST-001")
        assert all(e['prd_id'] == 'TEST-001' for e in test001_entries)

    def test_verify_audit_chain(self, sample_prd_draft, patched_paths):
        """Test audit log hash chain verification."""
        # Create a chain of entries
        for i in range(3):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="TEST-001",
                prd_dir=sample_prd_draft
            )

        is_valid, issues = prd_manager.verify_audit_chain()
        assert is_valid is True
        assert len(issues) == 0


# ============================================================================
# Test: Template Functions
# ============================================================================


class TestTemplates:
    """Tests for PRD template functions."""

    def test_create_prd_template_feature(self):
        """Test creating feature PRD template."""
        template = prd_manager.create_prd_template("TEST-100", "Test Feature", "feature")

        assert 'project' in template
        assert 'branchName' in template
        assert 'userStories' in template
        assert "feature/" in template['branchName']

    def test_create_prd_template_bugfix(self):
        """Test creating bugfix PRD template."""
        template = prd_manager.create_prd_template("BUG-100", "Fix Bug", "bugfix")

        assert 'project' in template
        assert 'branchName' in template
        # Bugfix uses 'fix/' prefix
        assert "fix/" in template['branchName'] or "bugfix/" in template['branchName'].lower()

    def test_create_manifest_template(self):
        """Test creating manifest template."""
        manifest = prd_manager.create_manifest_template(
            "TEST-100",
            "Test Feature",
            "test-owner",
            "feature",
            5
        )

        assert manifest['id'] == "TEST-100"
        assert manifest['title'] == "Test Feature"
        assert manifest['status'] == "draft"
        assert manifest['owner'] == "test-owner"
        assert manifest['story_count'] == 5


# ============================================================================
# Test: Format Functions
# ============================================================================


class TestFormatFunctions:
    """Tests for output formatting functions."""

    def test_format_prd_table_empty(self):
        """Test formatting empty PRD list."""
        output = prd_manager.format_prd_table([])
        assert "No PRDs found" in output

    def test_format_prd_table_with_data(self, sample_prd_draft, patched_paths):
        """Test formatting PRD table with data."""
        info = prd_manager.get_prd_info(sample_prd_draft)
        output = prd_manager.format_prd_table([info])

        assert "TEST-001" in output
        assert "Test Feature" in output
        assert "draft" in output.lower()

    def test_format_prd_detail(self, sample_prd_draft, patched_paths):
        """Test formatting PRD details."""
        info = prd_manager.get_prd_info(sample_prd_draft)
        output = prd_manager.format_prd_detail(info)

        assert "TEST-001" in output
        assert "Test Feature" in output
        assert "draft" in output.lower()
        assert "test-user" in output
