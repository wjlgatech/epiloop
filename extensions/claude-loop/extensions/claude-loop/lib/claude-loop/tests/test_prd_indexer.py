#!/usr/bin/env python3
"""
test_prd_indexer.py - Tests for PRD Indexer

Tests the indexing functionality of prd-indexer.py:
- rebuild command: building index from filesystem
- verify command: validating index matches filesystem
- show command: displaying indexed PRDs
- stats command: showing index statistics

Usage:
    pytest tests/test_prd_indexer.py -v
    pytest tests/test_prd_indexer.py::TestBuildIndex -v
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# Add lib to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import prd-indexer module
import importlib.util
spec = importlib.util.spec_from_file_location("prd_indexer", lib_path / "prd-indexer.py")
if spec and spec.loader:
    sys.modules["prd_indexer"] = importlib.util.module_from_spec(spec)
    prd_indexer = sys.modules["prd_indexer"]
    spec.loader.exec_module(prd_indexer)


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
    prd_dir = temp_prds_dir / "drafts" / "index-test-draft"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "index-test-draft",
        "branchName": "feature/idx-001",
        "description": "A test PRD for indexing",
        "userStories": [
            {
                "id": "IDX-001",
                "title": "Index Story 1",
                "description": "Test story",
                "acceptanceCriteria": ["Test criterion"],
                "priority": 1,
                "passes": False,
                "notes": ""
            },
            {
                "id": "IDX-002",
                "title": "Index Story 2",
                "description": "Another test story",
                "acceptanceCriteria": ["Another criterion"],
                "priority": 2,
                "passes": True,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Create MANIFEST.yaml
    manifest = {
        "id": "IDX-001",
        "title": "Index Test Draft",
        "status": "draft",
        "owner": "indexer-test",
        "created_at": "2026-01-05T00:00:00Z",
        "updated_at": "2026-01-05T00:00:00Z",
        "tags": ["test", "indexing"],
        "priority": "medium",
        "description": "A test PRD for indexing",
        "story_count": 2,
        "completed_stories": 1,
        "branch_name": "feature/idx-001"
    }

    import yaml
    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    return prd_dir


@pytest.fixture
def sample_prd_active(temp_prds_dir):
    """Create a sample active PRD."""
    prd_dir = temp_prds_dir / "active" / "index-test-active"
    prd_dir.mkdir(parents=True)

    # Create prd.json
    prd_json = {
        "project": "index-test-active",
        "branchName": "feature/idx-active",
        "description": "An active test PRD",
        "userStories": [
            {
                "id": "ACT-IDX-001",
                "title": "Active Index Story",
                "description": "Active test story",
                "acceptanceCriteria": ["Active criterion"],
                "priority": 1,
                "passes": True,
                "notes": ""
            }
        ]
    }

    with open(prd_dir / "prd.json", 'w') as f:
        json.dump(prd_json, f, indent=2)

    # Create MANIFEST.yaml
    manifest = {
        "id": "ACT-IDX",
        "title": "Index Test Active",
        "status": "active",
        "owner": "indexer-test",
        "created_at": "2026-01-04T00:00:00Z",
        "approved_at": "2026-01-05T00:00:00Z",
        "updated_at": "2026-01-05T00:00:00Z",
        "tags": ["active", "indexing"],
        "priority": "high",
        "description": "An active test PRD",
        "story_count": 1,
        "completed_stories": 1,
        "branch_name": "feature/idx-active"
    }

    import yaml
    with open(prd_dir / "MANIFEST.yaml", 'w') as f:
        yaml.dump(manifest, f)

    return prd_dir


@pytest.fixture
def patched_paths(temp_prds_dir, monkeypatch):
    """Patch module paths to use temporary directories."""
    project_root = temp_prds_dir.parent
    monkeypatch.setattr(prd_indexer, 'PRDS_DIR', temp_prds_dir)
    monkeypatch.setattr(prd_indexer, 'PROJECT_ROOT', project_root)
    monkeypatch.setattr(prd_indexer, 'CLAUDE_LOOP_DIR', project_root / ".claude-loop")
    monkeypatch.setattr(prd_indexer, 'INDEX_FILE', project_root / ".claude-loop" / "prd-index.json")
    return temp_prds_dir


# ============================================================================
# Test: Build Index Entry
# ============================================================================


class TestBuildIndexEntry:
    """Tests for building individual index entries."""

    def test_build_entry_from_draft(self, sample_prd_draft, patched_paths):
        """Test building index entry from draft PRD."""
        entry = prd_indexer.build_index_entry(sample_prd_draft)

        assert entry is not None
        assert entry.id == "IDX-001"
        assert entry.title == "Index Test Draft"
        assert entry.status == "draft"
        assert entry.owner == "indexer-test"
        assert entry.story_count == 2
        assert entry.completed_stories == 1
        assert "test" in entry.tags
        assert "indexing" in entry.tags

    def test_build_entry_from_active(self, sample_prd_active, patched_paths):
        """Test building index entry from active PRD."""
        entry = prd_indexer.build_index_entry(sample_prd_active)

        assert entry is not None
        assert entry.id == "ACT-IDX"
        assert entry.status == "active"

    def test_build_entry_missing_manifest(self, temp_prds_dir, patched_paths):
        """Test that missing manifest returns None."""
        empty_dir = temp_prds_dir / "drafts" / "no-manifest"
        empty_dir.mkdir(parents=True)

        entry = prd_indexer.build_index_entry(empty_dir)
        assert entry is None

    def test_build_entry_includes_hashes(self, sample_prd_draft, patched_paths):
        """Test that index entries include file hashes."""
        entry = prd_indexer.build_index_entry(sample_prd_draft)

        assert entry is not None
        assert entry.manifest_hash is not None
        assert len(entry.manifest_hash) == 64  # SHA256 hex length
        assert entry.prd_json_hash is not None
        assert len(entry.prd_json_hash) == 64


# ============================================================================
# Test: Scan PRDs for Index
# ============================================================================


class TestScanPRDsForIndex:
    """Tests for scanning PRDs directory."""

    def test_scan_empty_directory(self, temp_prds_dir, patched_paths):
        """Test scanning empty PRDs directory."""
        entries = prd_indexer.scan_prds_for_index(temp_prds_dir)
        assert len(entries) == 0

    def test_scan_with_prds(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test scanning directory with PRDs."""
        entries = prd_indexer.scan_prds_for_index(temp_prds_dir)

        assert len(entries) == 2

        # Check we have both PRDs
        ids = {e.id for e in entries}
        assert "IDX-001" in ids
        assert "ACT-IDX" in ids

    def test_scan_ignores_hidden_dirs(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test that hidden directories are ignored."""
        hidden_dir = temp_prds_dir / "drafts" / ".hidden-prd"
        hidden_dir.mkdir(parents=True)

        # Create a manifest in hidden dir
        import yaml
        manifest = {"id": "HIDDEN-001", "title": "Hidden", "status": "draft", "owner": "test"}
        with open(hidden_dir / "MANIFEST.yaml", 'w') as f:
            yaml.dump(manifest, f)

        entries = prd_indexer.scan_prds_for_index(temp_prds_dir)

        # Should only find the sample PRD, not the hidden one
        ids = {e.id for e in entries}
        assert "HIDDEN-001" not in ids


# ============================================================================
# Test: Build Index
# ============================================================================


class TestBuildIndex:
    """Tests for building complete index."""

    def test_build_index_empty(self, temp_prds_dir, patched_paths):
        """Test building index from empty directory."""
        index = prd_indexer.build_index(temp_prds_dir)

        assert index.total_prds == 0
        assert len(index.entries) == 0
        assert index.version == "1.0"

    def test_build_index_with_prds(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test building index with PRDs."""
        index = prd_indexer.build_index(temp_prds_dir)

        assert index.total_prds == 2
        assert len(index.entries) == 2

        # Check by_status counts
        assert index.by_status.get('draft', 0) == 1
        assert index.by_status.get('active', 0) == 1

    def test_build_index_has_timestamp(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test that index includes generation timestamp."""
        index = prd_indexer.build_index(temp_prds_dir)

        assert index.generated_at is not None
        assert len(index.generated_at) > 0
        # Should be ISO format
        assert "T" in index.generated_at
        assert "Z" in index.generated_at


# ============================================================================
# Test: Save and Load Index
# ============================================================================


class TestSaveLoadIndex:
    """Tests for index save/load operations."""

    def test_save_index(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test saving index to file."""
        index = prd_indexer.build_index(temp_prds_dir)
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"

        result = prd_indexer.save_index(index, index_path)

        assert result is True
        assert index_path.exists()

    def test_load_index(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test loading index from file."""
        index = prd_indexer.build_index(temp_prds_dir)
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"

        prd_indexer.save_index(index, index_path)
        loaded = prd_indexer.load_index(index_path)

        assert loaded is not None
        assert loaded['total_prds'] == 1
        assert len(loaded['entries']) == 1

    def test_load_nonexistent_index(self, temp_prds_dir, patched_paths):
        """Test loading nonexistent index returns None."""
        index_path = temp_prds_dir.parent / ".claude-loop" / "nonexistent.json"
        loaded = prd_indexer.load_index(index_path)
        assert loaded is None


# ============================================================================
# Test: Verify Index
# ============================================================================


class TestVerifyIndex:
    """Tests for index verification."""

    def test_verify_valid_index(self, temp_prds_dir, sample_prd_draft, sample_prd_active, patched_paths):
        """Test verifying a valid index."""
        # Build and save index
        index = prd_indexer.build_index(temp_prds_dir)
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"
        prd_indexer.save_index(index, index_path)

        # Verify
        results = prd_indexer.verify_index(temp_prds_dir, index_path)

        assert results['verified'] is True
        assert len(results['issues']) == 0

    def test_verify_missing_from_index(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test verification detects PRDs missing from index."""
        # Create empty index
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"
        empty_index = {
            "version": "1.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "prds_directory": str(temp_prds_dir),
            "total_prds": 0,
            "by_status": {},
            "entries": []
        }
        with open(index_path, 'w') as f:
            json.dump(empty_index, f)

        # Verify - should detect PRD missing from index
        results = prd_indexer.verify_index(temp_prds_dir, index_path)

        assert results['verified'] is False
        assert len(results['missing_from_index']) == 1
        assert results['missing_from_index'][0]['id'] == "IDX-001"

    def test_verify_missing_from_filesystem(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test verification detects PRDs in index but not in filesystem."""
        # Build index with extra entry
        index = prd_indexer.build_index(temp_prds_dir)
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"

        # Add fake entry
        from dataclasses import asdict
        index_dict = asdict(index)
        index_dict['entries'].append({
            'id': 'FAKE-001',
            'title': 'Fake PRD',
            'status': 'draft',
            'owner': 'fake',
            'created_at': '2026-01-01T00:00:00Z',
            'path': str(temp_prds_dir / 'drafts' / 'fake'),
            'directory_name': 'fake'
        })
        index_dict['total_prds'] = len(index_dict['entries'])

        with open(index_path, 'w') as f:
            json.dump(index_dict, f, default=str)

        # Verify - should detect PRD missing from filesystem
        results = prd_indexer.verify_index(temp_prds_dir, index_path)

        assert results['verified'] is False
        assert len(results['missing_from_filesystem']) == 1
        assert results['missing_from_filesystem'][0]['id'] == "FAKE-001"

    def test_verify_hash_mismatch(self, temp_prds_dir, sample_prd_draft, patched_paths):
        """Test verification detects file content changes."""
        # Build and save index
        index = prd_indexer.build_index(temp_prds_dir)
        index_path = temp_prds_dir.parent / ".claude-loop" / "prd-index.json"
        prd_indexer.save_index(index, index_path)

        # Modify prd.json after indexing
        prd_json_path = sample_prd_draft / "prd.json"
        with open(prd_json_path, 'r') as f:
            data = json.load(f)

        data['description'] = "Modified after indexing"

        with open(prd_json_path, 'w') as f:
            json.dump(data, f)

        # Verify - should detect hash mismatch
        results = prd_indexer.verify_index(temp_prds_dir, index_path)

        assert results['verified'] is False
        assert len(results['hash_mismatches']) >= 1

    def test_verify_nonexistent_index(self, temp_prds_dir, patched_paths):
        """Test verification with nonexistent index file."""
        index_path = temp_prds_dir.parent / ".claude-loop" / "nonexistent.json"

        results = prd_indexer.verify_index(temp_prds_dir, index_path)

        assert results['verified'] is False
        assert any("not exist" in issue.lower() or "invalid" in issue.lower()
                   for issue in results['issues'])


# ============================================================================
# Test: File Hash Computation
# ============================================================================


class TestFileHashComputation:
    """Tests for file hash computation."""

    def test_compute_file_hash(self, sample_prd_draft):
        """Test computing hash of a file."""
        prd_json_path = sample_prd_draft / "prd.json"
        hash_value = prd_indexer.compute_file_hash(prd_json_path)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hex length

    def test_compute_file_hash_nonexistent(self, temp_prds_dir):
        """Test computing hash of nonexistent file returns None."""
        nonexistent = temp_prds_dir / "nonexistent.json"
        hash_value = prd_indexer.compute_file_hash(nonexistent)
        assert hash_value is None

    def test_hash_changes_with_content(self, sample_prd_draft):
        """Test that hash changes when content changes."""
        prd_json_path = sample_prd_draft / "prd.json"

        hash_before = prd_indexer.compute_file_hash(prd_json_path)

        # Modify file
        with open(prd_json_path, 'r') as f:
            data = json.load(f)
        data['description'] = "Modified content"
        with open(prd_json_path, 'w') as f:
            json.dump(data, f)

        hash_after = prd_indexer.compute_file_hash(prd_json_path)

        assert hash_before != hash_after


# ============================================================================
# Test: Index Entry Dataclass
# ============================================================================


class TestPRDIndexEntry:
    """Tests for PRDIndexEntry dataclass."""

    def test_entry_default_values(self):
        """Test PRDIndexEntry default values."""
        entry = prd_indexer.PRDIndexEntry(
            id="TEST-001",
            title="Test",
            status="draft",
            owner="tester",
            created_at="2026-01-01",
            path="/test/path",
            directory_name="test"
        )

        assert entry.tags == []
        assert entry.story_count == 0
        assert entry.completed_stories == 0
        assert entry.branch_name is None

    def test_entry_with_all_fields(self):
        """Test PRDIndexEntry with all fields."""
        entry = prd_indexer.PRDIndexEntry(
            id="TEST-002",
            title="Full Test",
            status="active",
            owner="tester",
            created_at="2026-01-01",
            path="/test/path",
            directory_name="full-test",
            tags=["tag1", "tag2"],
            story_count=5,
            completed_stories=3,
            branch_name="feature/test",
            priority="high",
            description="A full test entry",
            manifest_hash="abc123",
            prd_json_hash="def456"
        )

        assert entry.id == "TEST-002"
        assert len(entry.tags) == 2
        assert entry.story_count == 5
        assert entry.priority == "high"


# ============================================================================
# Test: PRDIndex Dataclass
# ============================================================================


class TestPRDIndex:
    """Tests for PRDIndex dataclass."""

    def test_index_default_values(self):
        """Test PRDIndex default values."""
        index = prd_indexer.PRDIndex()

        assert index.version == "1.0"
        assert index.total_prds == 0
        assert index.entries == []
        assert index.by_status == {}

    def test_index_with_entries(self):
        """Test PRDIndex with entries."""
        entry1 = {"id": "TEST-001", "status": "draft"}
        entry2 = {"id": "TEST-002", "status": "active"}

        index = prd_indexer.PRDIndex(
            version="1.0",
            generated_at="2026-01-01T00:00:00Z",
            prds_directory="/test/prds",
            total_prds=2,
            by_status={"draft": 1, "active": 1},
            entries=[entry1, entry2]
        )

        assert index.total_prds == 2
        assert len(index.entries) == 2
        assert index.by_status['draft'] == 1
