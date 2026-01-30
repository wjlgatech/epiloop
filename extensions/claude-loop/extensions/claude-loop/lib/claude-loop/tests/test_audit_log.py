#!/usr/bin/env python3
"""
test_audit_log.py - Tests for Audit Log and Integrity Verification

Tests the audit log functionality from prd-manager.py:
- Audit entry creation and chaining
- Hash chain verification
- Tamper detection
- Integrity issue detection and fixing

Usage:
    pytest tests/test_audit_log.py -v
    pytest tests/test_audit_log.py::TestAuditLogChain -v
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add lib to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import prd-manager module
import importlib.util
spec = importlib.util.spec_from_file_location("prd_manager", lib_path / "prd-manager.py")
if spec and spec.loader:
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
def sample_prd(temp_prds_dir):
    """Create a sample PRD for testing."""
    prd_dir = temp_prds_dir / "drafts" / "audit-test"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "audit-test",
        "branchName": "feature/audit-001",
        "description": "A test PRD for audit logging",
        "userStories": [
            {
                "id": "AUD-001",
                "title": "Audit Story",
                "description": "Test audit",
                "acceptanceCriteria": ["Test"],
                "priority": 1,
                "passes": False,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Create MANIFEST.yaml
    manifest = {
        "id": "AUD-001",
        "title": "Audit Test",
        "status": "draft",
        "owner": "audit-tester",
        "created_at": "2026-01-01T00:00:00Z"
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
    return temp_prds_dir


# ============================================================================
# Test: Audit Entry Creation
# ============================================================================


class TestAuditEntryCreation:
    """Tests for creating audit log entries."""

    def test_create_single_entry(self, sample_prd, patched_paths):
        """Test creating a single audit entry."""
        result = prd_manager.log_audit_entry(
            action="create",
            prd_id="AUD-001",
            prd_dir=sample_prd,
            actor="test-user",
            details={"test_key": "test_value"}
        )

        assert result is True
        assert prd_manager.AUDIT_LOG_FILE.exists()

        # Read and verify
        with open(prd_manager.AUDIT_LOG_FILE) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry['action'] == 'create'
        assert entry['prd_id'] == 'AUD-001'
        assert entry['actor'] == 'test-user'
        assert entry['details']['test_key'] == 'test_value'

    def test_entry_has_required_fields(self, sample_prd, patched_paths):
        """Test that audit entries have all required fields."""
        prd_manager.log_audit_entry(
            action="test",
            prd_id="AUD-001",
            prd_dir=sample_prd
        )

        with open(prd_manager.AUDIT_LOG_FILE) as f:
            entry = json.loads(f.readline())

        required_fields = ['timestamp', 'action', 'prd_id', 'actor',
                          'content_hash', 'prd_path', 'entry_hash']
        for field in required_fields:
            assert field in entry, f"Missing required field: {field}"

    def test_entry_timestamp_format(self, sample_prd, patched_paths):
        """Test that timestamp is in ISO 8601 format."""
        prd_manager.log_audit_entry(
            action="test",
            prd_id="AUD-001",
            prd_dir=sample_prd
        )

        with open(prd_manager.AUDIT_LOG_FILE) as f:
            entry = json.loads(f.readline())

        timestamp = entry['timestamp']
        # Should be parseable as ISO format
        assert 'T' in timestamp
        assert timestamp.endswith('Z')

    def test_entry_content_hash(self, sample_prd, patched_paths):
        """Test that content hash is computed correctly."""
        prd_manager.log_audit_entry(
            action="test",
            prd_id="AUD-001",
            prd_dir=sample_prd
        )

        with open(prd_manager.AUDIT_LOG_FILE) as f:
            entry = json.loads(f.readline())

        # Content hash should be SHA256 hex (64 chars)
        assert len(entry['content_hash']) == 64

        # Verify it matches manual computation
        expected_hash = prd_manager.compute_content_hash(sample_prd)
        assert entry['content_hash'] == expected_hash


# ============================================================================
# Test: Audit Log Hash Chain
# ============================================================================


class TestAuditLogChain:
    """Tests for audit log hash chain integrity."""

    def test_first_entry_has_no_previous(self, sample_prd, patched_paths):
        """Test that first entry has no previous hash."""
        prd_manager.log_audit_entry(
            action="first",
            prd_id="AUD-001",
            prd_dir=sample_prd
        )

        with open(prd_manager.AUDIT_LOG_FILE) as f:
            entry = json.loads(f.readline())

        assert entry['previous_hash'] is None

    def test_chain_links_correctly(self, sample_prd, patched_paths):
        """Test that hash chain links entries correctly."""
        # Create multiple entries
        for i in range(3):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        with open(prd_manager.AUDIT_LOG_FILE) as f:
            entries = [json.loads(line) for line in f]

        # First entry has no previous
        assert entries[0]['previous_hash'] is None

        # Each subsequent entry links to previous
        for i in range(1, len(entries)):
            assert entries[i]['previous_hash'] == entries[i-1]['entry_hash']

    def test_chain_verification_valid(self, sample_prd, patched_paths):
        """Test that valid chain passes verification."""
        # Create chain
        for i in range(5):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        is_valid, issues = prd_manager.verify_audit_chain()

        assert is_valid is True
        assert len(issues) == 0

    def test_chain_detects_tampered_entry(self, sample_prd, patched_paths):
        """Test that tampered entries are detected."""
        # Create chain
        for i in range(3):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        # Tamper with middle entry
        with open(prd_manager.AUDIT_LOG_FILE) as f:
            lines = f.readlines()

        entry = json.loads(lines[1])
        entry['action'] = 'TAMPERED'  # Modify without updating hash

        lines[1] = json.dumps(entry) + '\n'

        with open(prd_manager.AUDIT_LOG_FILE, 'w') as f:
            f.writelines(lines)

        # Verify should fail
        is_valid, issues = prd_manager.verify_audit_chain()

        assert is_valid is False
        assert len(issues) > 0
        assert any('mismatch' in issue.lower() or 'tamper' in issue.lower()
                   for issue in issues)

    def test_chain_detects_broken_link(self, sample_prd, patched_paths):
        """Test that broken chain links are detected."""
        # Create chain
        for i in range(3):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        # Break chain by modifying previous_hash
        with open(prd_manager.AUDIT_LOG_FILE) as f:
            lines = f.readlines()

        entry = json.loads(lines[2])
        entry['previous_hash'] = 'invalid_hash_12345'

        lines[2] = json.dumps(entry) + '\n'

        with open(prd_manager.AUDIT_LOG_FILE, 'w') as f:
            f.writelines(lines)

        # Verify should fail
        is_valid, issues = prd_manager.verify_audit_chain()

        assert is_valid is False
        assert any('chain broken' in issue.lower() or 'mismatch' in issue.lower()
                   for issue in issues)


# ============================================================================
# Test: Read Audit Log
# ============================================================================


class TestReadAuditLog:
    """Tests for reading audit log entries."""

    def test_read_all_entries(self, sample_prd, patched_paths):
        """Test reading all audit log entries."""
        # Create entries
        for i in range(5):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        entries = prd_manager.read_audit_log()

        assert len(entries) == 5
        # Should be newest first
        assert entries[0]['action'] == 'action_4'

    def test_read_with_limit(self, sample_prd, patched_paths):
        """Test reading with limit."""
        for i in range(10):
            prd_manager.log_audit_entry(
                action=f"action_{i}",
                prd_id="AUD-001",
                prd_dir=sample_prd
            )

        entries = prd_manager.read_audit_log(limit=3)

        assert len(entries) == 3

    def test_read_filter_by_prd_id(self, sample_prd, patched_paths):
        """Test filtering by PRD ID."""
        prd_manager.log_audit_entry(action="create", prd_id="AUD-001", prd_dir=sample_prd)
        prd_manager.log_audit_entry(action="approve", prd_id="AUD-002", prd_dir=sample_prd)
        prd_manager.log_audit_entry(action="complete", prd_id="AUD-001", prd_dir=sample_prd)

        entries = prd_manager.read_audit_log(prd_id="AUD-001")

        assert len(entries) == 2
        assert all(e['prd_id'] == 'AUD-001' for e in entries)

    def test_read_filter_by_action(self, sample_prd, patched_paths):
        """Test filtering by action type."""
        prd_manager.log_audit_entry(action="create", prd_id="AUD-001", prd_dir=sample_prd)
        prd_manager.log_audit_entry(action="approve", prd_id="AUD-002", prd_dir=sample_prd)
        prd_manager.log_audit_entry(action="create", prd_id="AUD-003", prd_dir=sample_prd)

        entries = prd_manager.read_audit_log(action="create")

        assert len(entries) == 2
        assert all(e['action'] == 'create' for e in entries)

    def test_read_empty_log(self, temp_prds_dir, patched_paths):
        """Test reading empty audit log."""
        entries = prd_manager.read_audit_log()
        assert len(entries) == 0


# ============================================================================
# Test: Content Hash Computation
# ============================================================================


class TestContentHashComputation:
    """Tests for PRD content hash computation."""

    def test_compute_content_hash(self, sample_prd):
        """Test computing content hash of PRD directory."""
        hash_value = prd_manager.compute_content_hash(sample_prd)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hex length

    def test_hash_changes_with_prd_json(self, sample_prd):
        """Test that hash changes when prd.json changes."""
        hash_before = prd_manager.compute_content_hash(sample_prd)

        # Modify prd.json
        prd_json_path = sample_prd / "prd.json"
        with open(prd_json_path) as f:
            data = json.load(f)
        data['description'] = 'Modified content'
        with open(prd_json_path, 'w') as f:
            json.dump(data, f)

        hash_after = prd_manager.compute_content_hash(sample_prd)

        assert hash_before != hash_after

    def test_hash_changes_with_manifest(self, sample_prd):
        """Test that hash changes when MANIFEST.yaml changes."""
        hash_before = prd_manager.compute_content_hash(sample_prd)

        # Modify manifest
        import yaml
        manifest_path = sample_prd / "MANIFEST.yaml"
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        manifest['title'] = 'Modified Title'
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f)

        hash_after = prd_manager.compute_content_hash(sample_prd)

        assert hash_before != hash_after


# ============================================================================
# Test: Entry Hash Computation
# ============================================================================


class TestEntryHashComputation:
    """Tests for audit entry hash computation."""

    def test_compute_entry_hash_no_previous(self):
        """Test computing entry hash without previous hash."""
        entry = {
            'timestamp': '2026-01-01T00:00:00Z',
            'action': 'test',
            'prd_id': 'TEST-001',
            'actor': 'tester',
            'content_hash': 'abc123',
            'prd_path': '/test/path',
            'previous_hash': None
        }

        hash_value = prd_manager.compute_entry_hash(entry, None)

        assert hash_value is not None
        assert len(hash_value) == 64

    def test_compute_entry_hash_with_previous(self):
        """Test computing entry hash with previous hash."""
        entry = {
            'timestamp': '2026-01-01T00:00:00Z',
            'action': 'test',
            'prd_id': 'TEST-001',
            'actor': 'tester',
            'content_hash': 'abc123',
            'prd_path': '/test/path',
            'previous_hash': 'previous_hash_value'
        }

        hash_without = prd_manager.compute_entry_hash(entry, None)
        hash_with = prd_manager.compute_entry_hash(entry, 'previous_hash_value')

        # Different previous hashes should produce different entry hashes
        assert hash_without != hash_with

    def test_entry_hash_is_deterministic(self):
        """Test that entry hash is deterministic."""
        entry = {
            'timestamp': '2026-01-01T00:00:00Z',
            'action': 'test',
            'prd_id': 'TEST-001',
            'actor': 'tester',
            'content_hash': 'abc123',
            'prd_path': '/test/path',
            'previous_hash': None
        }

        hash1 = prd_manager.compute_entry_hash(entry, None)
        hash2 = prd_manager.compute_entry_hash(entry, None)

        assert hash1 == hash2


# ============================================================================
# Test: Integrity Issues
# ============================================================================


class TestIntegrityIssues:
    """Tests for integrity issue detection."""

    def test_integrity_issue_dataclass(self):
        """Test IntegrityIssue dataclass."""
        issue = prd_manager.IntegrityIssue(
            prd_id="TEST-001",
            issue_type="hash_mismatch",
            description="Test issue",
            current_value="abc",
            expected_value="def",
            fixable=True,
            prd_path="/test/path"
        )

        assert issue.prd_id == "TEST-001"
        assert issue.issue_type == "hash_mismatch"
        assert issue.fixable is True

    def test_verify_all_prds_empty(self, temp_prds_dir, patched_paths):
        """Test verifying empty PRDs directory."""
        issues = prd_manager.verify_all_prds(temp_prds_dir)
        assert len(issues) == 0

    def test_verify_all_prds_with_issues(self, temp_prds_dir, patched_paths):
        """Test verifying PRDs with issues."""
        # Create active PRD without approval hash
        prd_dir = temp_prds_dir / "active" / "no-approval"
        prd_dir.mkdir(parents=True)

        prd_json = {"project": "test", "userStories": []}
        with open(prd_dir / "prd.json", 'w') as f:
            json.dump(prd_json, f)

        import yaml
        manifest = {
            "id": "NOAPP-001",
            "title": "No Approval",
            "status": "active",  # Active but no approval block
            "owner": "test"
        }
        with open(prd_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        issues = prd_manager.verify_all_prds(temp_prds_dir)

        assert len(issues) > 0
        assert any(i.issue_type == 'missing_approval' for i in issues)


# ============================================================================
# Test: Fix PRD Hash
# ============================================================================


class TestFixPRDHash:
    """Tests for fixing PRD approval hashes."""

    def test_fix_hash_dry_run(self, temp_prds_dir, patched_paths):
        """Test fix hash in dry run mode."""
        # Create active PRD with wrong hash
        prd_dir = temp_prds_dir / "active" / "wrong-hash"
        prd_dir.mkdir(parents=True)

        prd_json = {"project": "test", "userStories": []}
        with open(prd_dir / "prd.json", 'w') as f:
            json.dump(prd_json, f)

        import yaml
        manifest = {
            "id": "WRONG-001",
            "status": "active",
            "owner": "test",
            "approval": {
                "approved_by": "approver",
                "approval_hash": "wrong_hash_value"
            }
        }
        with open(prd_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        success, message = prd_manager.fix_prd_hash(prd_dir, dry_run=True)

        assert success is True
        assert "Would update" in message

        # Verify hash wasn't actually changed
        with open(prd_dir / "MANIFEST.yaml") as f:
            updated = yaml.safe_load(f)
        assert updated['approval']['approval_hash'] == "wrong_hash_value"

    def test_fix_hash_actual(self, temp_prds_dir, patched_paths):
        """Test actually fixing hash."""
        # Create active PRD with wrong hash
        prd_dir = temp_prds_dir / "active" / "fix-hash"
        prd_dir.mkdir(parents=True)

        prd_json = {"project": "test", "userStories": []}
        with open(prd_dir / "prd.json", 'w') as f:
            json.dump(prd_json, f)

        import yaml
        manifest = {
            "id": "FIX-001",
            "status": "active",
            "owner": "test",
            "approval": {
                "approved_by": "approver",
                "approval_hash": "wrong_hash"
            }
        }
        with open(prd_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        success, message = prd_manager.fix_prd_hash(prd_dir, dry_run=False)

        assert success is True

        # Verify hash was fixed
        with open(prd_dir / "MANIFEST.yaml") as f:
            updated = yaml.safe_load(f)

        expected_hash = prd_manager.compute_prd_hash(prd_dir / "prd.json")
        assert updated['approval']['approval_hash'] == expected_hash

    def test_fix_hash_missing_manifest(self, temp_prds_dir, patched_paths):
        """Test fix hash with missing manifest."""
        prd_dir = temp_prds_dir / "active" / "no-manifest"
        prd_dir.mkdir(parents=True)

        success, message = prd_manager.fix_prd_hash(prd_dir)

        assert success is False
        assert "not found" in message.lower()

    def test_fix_hash_missing_prd_json(self, temp_prds_dir, patched_paths):
        """Test fix hash with missing prd.json."""
        prd_dir = temp_prds_dir / "active" / "no-prd-json"
        prd_dir.mkdir(parents=True)

        import yaml
        manifest = {"id": "TEST", "status": "active"}
        with open(prd_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        success, message = prd_manager.fix_prd_hash(prd_dir)

        assert success is False
        assert "not found" in message.lower()
