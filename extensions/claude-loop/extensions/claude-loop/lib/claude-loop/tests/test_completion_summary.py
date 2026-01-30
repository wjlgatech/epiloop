#!/usr/bin/env python3
"""
Tests for lib/completion-summary.py (INV-010)

Tests cover:
- PRD loading and story analysis
- Session state loading
- Metrics loading and aggregation
- Artifact detection
- Auto-detection info gathering
- Completion summary generation
- Terminal and JSON output rendering
"""

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

# Load completion-summary.py module
lib_dir = Path(__file__).parent.parent / "lib"
spec = importlib.util.spec_from_file_location(
    "completion_summary",
    lib_dir / "completion-summary.py"
)
assert spec is not None and spec.loader is not None
completion_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion_summary)


# ============================================================================
# Test Data
# ============================================================================

SAMPLE_PRD = {
    "project": "test-project",
    "branchName": "feature/test-branch",
    "description": "A test project for completion summary testing",
    "userStories": [
        {
            "id": "TS-001",
            "title": "First Story",
            "priority": 1,
            "passes": True,
            "notes": "Implemented in commit abc1234"
        },
        {
            "id": "TS-002",
            "title": "Second Story",
            "priority": 2,
            "passes": True,
            "notes": "Implemented in commit def5678"
        },
        {
            "id": "TS-003",
            "title": "Third Story",
            "priority": 3,
            "passes": False,
            "notes": ""
        },
    ]
}

COMPLETE_PRD = {
    "project": "complete-project",
    "branchName": "feature/complete-feature",
    "description": "A fully completed project",
    "userStories": [
        {
            "id": "US-001",
            "title": "Story One",
            "priority": 1,
            "passes": True,
            "notes": ""
        },
        {
            "id": "US-002",
            "title": "Story Two",
            "priority": 2,
            "passes": True,
            "notes": ""
        },
    ]
}

EMPTY_PRD = {
    "project": "empty-project",
    "branchName": "feature/empty",
    "description": "Empty project",
    "userStories": []
}

SAMPLE_SESSION_STATE = {
    "session_id": "test_proj_20260112_143000",
    "project": "test-project",
    "branch": "feature/test-branch",
    "prd_file": "/path/to/prd.json",
    "current_phase": "implementation",
    "current_story": "TS-002",
    "current_iteration": 5,
    "started_at": "2026-01-12T14:30:00Z",
    "last_saved_at": "2026-01-12T15:45:00Z",
    "stories_completed": 2,
    "stories_total": 3,
    "auto_save_enabled": True
}

SAMPLE_METRICS = {
    "iterations": [
        {
            "story_id": "TS-001",
            "tokens_in": 5000,
            "tokens_out": 2000,
            "agents": ["test-runner", "debugger"],
            "model": "opus"
        },
        {
            "story_id": "TS-002",
            "tokens_in": 4500,
            "tokens_out": 1800,
            "agents": ["code-reviewer"],
            "model": "sonnet"
        },
    ],
    "summary": {
        "total_duration_ms": 120000,
        "total_cost_usd": 0.45,
        "model_counts": {
            "opus": 1,
            "sonnet": 1
        }
    }
}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_prd_file():
    """Create a temporary PRD file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE_PRD, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_complete_prd_file():
    """Create a temporary complete PRD file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(COMPLETE_PRD, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_empty_prd_file():
    """Create a temporary empty PRD file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(EMPTY_PRD, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_session_file():
    """Create a temporary session state file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE_SESSION_STATE, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_metrics_file():
    """Create a temporary metrics file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE_METRICS, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create architecture doc
        arch_dir = os.path.join(tmpdir, "docs", "architecture")
        os.makedirs(arch_dir)
        with open(os.path.join(arch_dir, "architecture.md"), 'w') as f:
            f.write("# Architecture\n\nTest architecture doc")

        # Create ADR directory with files
        adr_dir = os.path.join(tmpdir, "docs", "adrs")
        os.makedirs(adr_dir)
        with open(os.path.join(adr_dir, "001-use-rest-api.md"), 'w') as f:
            f.write("# ADR 001: Use REST API\n")
        with open(os.path.join(adr_dir, "002-jwt-auth.md"), 'w') as f:
            f.write("# ADR 002: JWT Authentication\n")

        yield tmpdir


# ============================================================================
# Test: Data Classes
# ============================================================================

class TestDataClasses:
    """Tests for data classes."""

    def test_story_metrics_creation(self):
        """Test StoryMetrics dataclass creation."""
        story = completion_summary.StoryMetrics(
            id="TS-001",
            title="Test Story",
            completed=True,
            commit_hash="abc1234",
            tests_added=5,
            files_changed=3
        )
        assert story.id == "TS-001"
        assert story.completed is True
        assert story.commit_hash == "abc1234"

    def test_execution_metrics_defaults(self):
        """Test ExecutionMetrics default values."""
        metrics = completion_summary.ExecutionMetrics()
        assert metrics.total_duration_ms == 0
        assert metrics.iterations_used == 0
        assert metrics.agents_invoked == []
        assert metrics.cost_usd == 0.0

    def test_artifact_info_creation(self):
        """Test ArtifactInfo dataclass creation."""
        artifact = completion_summary.ArtifactInfo(
            path="docs/architecture.md",
            artifact_type="architecture",
            size_bytes=1024
        )
        assert artifact.path == "docs/architecture.md"
        assert artifact.artifact_type == "architecture"

    def test_auto_detection_info_defaults(self):
        """Test AutoDetectionInfo default values."""
        info = completion_summary.AutoDetectionInfo()
        assert info.complexity_level == 2
        assert info.complexity_name == "medium"
        assert info.track == "standard"

    def test_completion_summary_to_dict(self):
        """Test CompletionSummary to_dict method."""
        summary = completion_summary.CompletionSummary(
            project_name="test",
            branch_name="feature/test",
            completed_at="2026-01-12T10:00:00Z",
            stories_total=5,
            stories_completed=3,
            stories_failed=2
        )
        result = summary.to_dict()
        assert result["project_name"] == "test"
        assert result["stories"]["total"] == 5
        assert result["stories"]["completed"] == 3


# ============================================================================
# Test: File Loading
# ============================================================================

class TestFileLoading:
    """Tests for file loading functions."""

    def test_load_prd(self, temp_prd_file):
        """Test loading a valid PRD file."""
        prd_data = completion_summary.load_prd(temp_prd_file)
        assert prd_data["project"] == "test-project"
        assert len(prd_data["userStories"]) == 3

    def test_load_prd_nonexistent(self):
        """Test loading a nonexistent PRD file."""
        with pytest.raises(FileNotFoundError):
            completion_summary.load_prd("/nonexistent/path.json")

    def test_load_session_state(self, temp_session_file):
        """Test loading a valid session state file."""
        session_data = completion_summary.load_session_state(temp_session_file)
        assert session_data["project"] == "test-project"
        assert session_data["current_iteration"] == 5

    def test_load_metrics(self, temp_metrics_file):
        """Test loading a valid metrics file."""
        metrics = completion_summary.load_metrics(temp_metrics_file)
        assert len(metrics["iterations"]) == 2
        assert metrics["summary"]["total_cost_usd"] == 0.45


# ============================================================================
# Test: PRD Analysis
# ============================================================================

class TestPRDAnalysis:
    """Tests for PRD analysis functions."""

    def test_analyze_prd_partial_complete(self):
        """Test analyzing PRD with partial completion."""
        stories, total, completed, failed = completion_summary.analyze_prd(SAMPLE_PRD)

        assert total == 3
        assert completed == 2
        assert failed == 1
        assert len(stories) == 3

        # Check individual stories
        assert stories[0].id == "TS-001"
        assert stories[0].completed is True
        assert stories[2].completed is False

    def test_analyze_prd_all_complete(self):
        """Test analyzing PRD with all stories complete."""
        _stories, total, completed, failed = completion_summary.analyze_prd(COMPLETE_PRD)

        assert total == 2
        assert completed == 2
        assert failed == 0

    def test_analyze_prd_empty(self):
        """Test analyzing empty PRD."""
        stories, total, completed, failed = completion_summary.analyze_prd(EMPTY_PRD)

        assert total == 0
        assert completed == 0
        assert failed == 0
        assert stories == []

    def test_analyze_prd_extracts_commit_hash(self):
        """Test that commit hash is extracted from notes."""
        stories, _, _, _ = completion_summary.analyze_prd(SAMPLE_PRD)

        # First story has commit hash in notes
        assert stories[0].commit_hash == "abc1234"


# ============================================================================
# Test: Artifact Detection
# ============================================================================

class TestArtifactDetection:
    """Tests for artifact detection functions."""

    def test_detect_artifacts_with_docs(self, temp_project_dir):
        """Test detecting artifacts in project with documentation."""
        artifacts = completion_summary.detect_artifacts(temp_project_dir)

        # Should find architecture.md and 2 ADRs
        assert len(artifacts) >= 3

        # Check artifact types
        arch_artifacts = [a for a in artifacts if a.artifact_type == "architecture"]
        adr_artifacts = [a for a in artifacts if a.artifact_type == "adr"]

        assert len(arch_artifacts) == 1
        assert len(adr_artifacts) == 2

    def test_detect_artifacts_empty_dir(self):
        """Test detecting artifacts in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = completion_summary.detect_artifacts(tmpdir)
            assert artifacts == []

    def test_artifact_has_size(self, temp_project_dir):
        """Test that detected artifacts have file size."""
        artifacts = completion_summary.detect_artifacts(temp_project_dir)

        for artifact in artifacts:
            assert artifact.size_bytes > 0


# ============================================================================
# Test: Summary Generation
# ============================================================================

class TestSummaryGeneration:
    """Tests for completion summary generation."""

    def test_generate_summary_from_prd(self, temp_prd_file):
        """Test generating summary from PRD file."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        assert summary.project_name == "test-project"
        assert summary.branch_name == "feature/test-branch"
        assert summary.stories_total == 3
        assert summary.stories_completed == 2
        assert summary.stories_failed == 1

    def test_generate_summary_from_session(self, temp_prd_file, temp_session_file):
        """Test generating summary with session state."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file,
            session_path=temp_session_file
        )

        assert summary.execution.iterations_used == 5

    def test_generate_summary_from_metrics(self, temp_prd_file, temp_metrics_file):
        """Test generating summary with metrics file."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file,
            metrics_path=temp_metrics_file
        )

        assert summary.execution.iterations_used == 2
        assert summary.execution.tokens_in == 9500  # 5000 + 4500
        assert summary.execution.tokens_out == 3800  # 2000 + 1800
        assert summary.execution.cost_usd == 0.45
        assert "test-runner" in summary.execution.agents_invoked
        assert "debugger" in summary.execution.agents_invoked
        assert "code-reviewer" in summary.execution.agents_invoked

    def test_generate_summary_success_status(self, temp_complete_prd_file):
        """Test summary success status for complete PRD."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_complete_prd_file
        )

        assert summary.success is True
        assert "successfully" in summary.status_message.lower()

    def test_generate_summary_incomplete_status(self, temp_prd_file):
        """Test summary status for incomplete PRD."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        assert summary.success is False
        assert "2/3" in summary.status_message

    def test_generate_summary_empty_prd_status(self, temp_empty_prd_file):
        """Test summary status for empty PRD."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_empty_prd_file
        )

        assert summary.success is False
        assert "no stories" in summary.status_message.lower()

    def test_generate_summary_with_artifacts(self, temp_prd_file, temp_project_dir):
        """Test summary includes detected artifacts."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file,
            project_dir=temp_project_dir
        )

        assert len(summary.artifacts_generated) >= 3


# ============================================================================
# Test: Rendering Functions
# ============================================================================

class TestRenderingFunctions:
    """Tests for rendering functions."""

    def test_format_duration_ms(self):
        """Test formatting milliseconds."""
        assert completion_summary.format_duration(500) == "500ms"

    def test_format_duration_seconds(self):
        """Test formatting seconds."""
        assert completion_summary.format_duration(5000) == "5.0s"

    def test_format_duration_minutes(self):
        """Test formatting minutes."""
        result = completion_summary.format_duration(125000)
        assert "2m" in result
        assert "5s" in result

    def test_format_duration_hours(self):
        """Test formatting hours."""
        result = completion_summary.format_duration(3665000)  # 1h 1m 5s
        assert "1h" in result
        assert "1m" in result

    def test_format_tokens_small(self):
        """Test formatting small token counts."""
        assert completion_summary.format_tokens(500) == "500"

    def test_format_tokens_thousands(self):
        """Test formatting thousands of tokens."""
        assert "K" in completion_summary.format_tokens(5000)

    def test_format_tokens_millions(self):
        """Test formatting millions of tokens."""
        assert "M" in completion_summary.format_tokens(1500000)

    def test_format_cost_small(self):
        """Test formatting small costs."""
        assert "$0.0045" == completion_summary.format_cost(0.0045)

    def test_format_cost_normal(self):
        """Test formatting normal costs."""
        assert "$1.23" == completion_summary.format_cost(1.23)


# ============================================================================
# Test: Summary Rendering
# ============================================================================

class TestSummaryRendering:
    """Tests for summary rendering."""

    def test_render_completion_summary(self, temp_prd_file):
        """Test rendering full completion summary."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        output = completion_summary.render_completion_summary(
            summary,
            colors=completion_summary.NO_COLORS  # Disable colors for testing
        )

        # Check key sections are present
        assert "COMPLETION SUMMARY" in output
        assert "test-project" in output
        assert "STORIES" in output
        assert "COMMITS" in output
        assert "ARTIFACTS" in output
        assert "EXECUTION" in output
        assert "AUTO-DETECTION" in output

    def test_render_completion_summary_verbose(self, temp_prd_file):
        """Test verbose rendering includes story details."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        output = completion_summary.render_completion_summary(
            summary,
            colors=completion_summary.NO_COLORS,
            verbose=True
        )

        # Verbose should show individual stories
        assert "TS-001" in output or "First Story" in output

    def test_render_completion_compact(self, temp_prd_file):
        """Test compact rendering."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        output = completion_summary.render_completion_compact(
            summary,
            colors=completion_summary.NO_COLORS
        )

        # Should be single line with key info
        assert "[COMPLETE]" in output
        assert "2/3 stories" in output
        assert "iterations" in output

    def test_render_with_colors(self, temp_prd_file):
        """Test rendering with colors enabled."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        output = completion_summary.render_completion_summary(
            summary,
            colors=completion_summary.COLORS
        )

        # Should contain ANSI escape codes
        assert "\033[" in output


# ============================================================================
# Test: JSON Output
# ============================================================================

class TestJSONOutput:
    """Tests for JSON output."""

    def test_summary_to_json(self, temp_prd_file):
        """Test converting summary to JSON."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        json_output = summary.to_dict()

        # Verify structure
        assert "project_name" in json_output
        assert "stories" in json_output
        assert "commits" in json_output
        assert "artifacts" in json_output
        assert "execution" in json_output
        assert "auto_detection" in json_output

    def test_json_serializable(self, temp_prd_file):
        """Test that summary dict is JSON serializable."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        # Should not raise
        json_str = json.dumps(summary.to_dict())
        assert json_str is not None

        # Should be parseable back
        parsed = json.loads(json_str)
        assert parsed["project_name"] == "test-project"


# ============================================================================
# Test: Auto-Detection
# ============================================================================

class TestAutoDetection:
    """Tests for auto-detection info gathering."""

    def test_get_auto_detection_info(self):
        """Test getting auto-detection info from PRD."""
        info = completion_summary.get_auto_detection_info(SAMPLE_PRD)

        # Should have default values at minimum
        assert info.complexity_level >= 0
        assert info.complexity_name is not None
        assert info.track is not None

    def test_auto_detection_in_summary(self, temp_prd_file):
        """Test auto-detection info included in summary."""
        summary = completion_summary.generate_completion_summary(
            prd_path=temp_prd_file
        )

        assert summary.auto_detection is not None
        assert summary.auto_detection.complexity_level >= 0


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_missing_optional_fields(self):
        """Test PRD with missing optional fields."""
        minimal_prd = {
            "userStories": [
                {"id": "US-001", "title": "Test"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(minimal_prd, f)
            f.flush()

            summary = completion_summary.generate_completion_summary(prd_path=f.name)

            # Should use defaults
            assert summary.project_name == "Unknown"
            assert summary.branch_name == ""

        os.unlink(f.name)

    def test_story_without_passes_field(self):
        """Test story without passes field defaults to incomplete."""
        prd = {
            "project": "test",
            "userStories": [
                {"id": "US-001", "title": "Test"}  # No passes field
            ]
        }

        stories, _, completed, failed = completion_summary.analyze_prd(prd)

        assert completed == 0
        assert failed == 1
        assert stories[0].completed is False

    def test_empty_metrics_iterations(self):
        """Test metrics file with empty iterations."""
        metrics = {"iterations": [], "summary": {}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metrics, f)
            f.flush()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as pf:
                json.dump(SAMPLE_PRD, pf)
                pf.flush()

                summary = completion_summary.generate_completion_summary(
                    prd_path=pf.name,
                    metrics_path=f.name
                )

                assert summary.execution.iterations_used == 0
                assert summary.execution.tokens_in == 0

            os.unlink(pf.name)
        os.unlink(f.name)


# ============================================================================
# Test: Count Functions
# ============================================================================

class TestCountFunctions:
    """Tests for count helper functions."""

    def test_count_tests_in_python_file(self):
        """Test counting tests in Python file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def test_one():
    pass

def test_two():
    pass

async def test_three():
    pass

class TestClass:
    def test_method(self):
        pass
""")
            f.flush()

            count = completion_summary.count_tests_in_file(f.name)
            assert count >= 3  # At least 3 test functions

        os.unlink(f.name)

    def test_count_tests_in_js_file(self):
        """Test counting tests in JavaScript file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write("""
describe('Suite', () => {
    it('should test one', () => {});
    test('should test two', () => {});
});
""")
            f.flush()

            count = completion_summary.count_tests_in_file(f.name)
            assert count >= 2  # describe + it + test

        os.unlink(f.name)

    def test_count_tests_nonexistent_file(self):
        """Test counting tests in nonexistent file returns 0."""
        count = completion_summary.count_tests_in_file("/nonexistent/file.py")
        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
