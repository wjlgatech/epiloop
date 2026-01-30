#!/usr/bin/env python3
"""
Tests for lib/progress-dashboard.py

Tests cover:
- PRD loading and parsing
- Story status detection
- Phase progress calculation
- Dashboard rendering (full and compact)
- Color mode toggling
- JSON output
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Load progress-dashboard.py module
lib_dir = Path(__file__).parent.parent / "lib"
spec = importlib.util.spec_from_file_location(
    "progress_dashboard",
    lib_dir / "progress-dashboard.py"
)
progress_dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress_dashboard)


# ============================================================================
# Test Data
# ============================================================================

SAMPLE_PRD = {
    "project": "test-project",
    "branchName": "feature/test-branch",
    "description": "A test project for dashboard testing",
    "userStories": [
        {
            "id": "TS-001",
            "title": "First Story",
            "priority": 1,
            "passes": True,
            "notes": "Completed successfully"
        },
        {
            "id": "TS-002",
            "title": "Second Story",
            "priority": 2,
            "passes": True,
            "notes": ""
        },
        {
            "id": "TS-003",
            "title": "Third Story",
            "priority": 3,
            "passes": False,
            "notes": ""
        },
        {
            "id": "TS-004",
            "title": "Fourth Story",
            "priority": 4,
            "passes": False,
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

LARGE_PRD = {
    "project": "large-project",
    "branchName": "feature/large",
    "description": "Large project with many stories for security compliance infrastructure",
    "userStories": [
        {
            "id": f"US-{i:03d}",
            "title": f"Story {i}",
            "priority": i,
            "passes": i <= 10,
            "notes": ""
        }
        for i in range(1, 21)
    ]
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
def temp_empty_prd_file():
    """Create a temporary empty PRD file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(EMPTY_PRD, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_large_prd_file():
    """Create a temporary large PRD file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(LARGE_PRD, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


# ============================================================================
# Test: PRD Loading
# ============================================================================

class TestPRDLoading:
    """Tests for PRD file loading."""

    def test_load_valid_prd(self, temp_prd_file):
        """Test loading a valid PRD file."""
        prd_data = progress_dashboard.load_prd(temp_prd_file)
        assert prd_data["project"] == "test-project"
        assert len(prd_data["userStories"]) == 4

    def test_load_nonexistent_prd(self):
        """Test loading a nonexistent PRD file raises error."""
        with pytest.raises(FileNotFoundError):
            progress_dashboard.load_prd("/nonexistent/path/prd.json")

    def test_load_invalid_json(self):
        """Test loading invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            f.flush()
            with pytest.raises(json.JSONDecodeError):
                progress_dashboard.load_prd(f.name)
            os.unlink(f.name)


# ============================================================================
# Test: Story Status Detection
# ============================================================================

class TestStoryStatus:
    """Tests for story status detection."""

    def test_complete_story(self):
        """Test detecting completed story."""
        story = {"id": "TS-001", "passes": True}
        status = progress_dashboard.get_story_status(story)
        assert status == "complete"

    def test_pending_story(self):
        """Test detecting pending story."""
        story = {"id": "TS-002", "passes": False}
        status = progress_dashboard.get_story_status(story)
        assert status == "pending"

    def test_running_story(self):
        """Test detecting currently running story."""
        story = {"id": "TS-003", "passes": False}
        status = progress_dashboard.get_story_status(story, current_story_id="TS-003")
        assert status == "running"

    def test_complete_story_even_if_current(self):
        """Test that completed stories stay complete even if marked current."""
        story = {"id": "TS-001", "passes": True}
        status = progress_dashboard.get_story_status(story, current_story_id="TS-001")
        assert status == "complete"

    def test_missing_passes_field(self):
        """Test handling story without passes field."""
        story = {"id": "TS-001"}
        status = progress_dashboard.get_story_status(story)
        assert status == "pending"


# ============================================================================
# Test: PRD Analysis
# ============================================================================

class TestPRDAnalysis:
    """Tests for PRD analysis."""

    def test_analyze_sample_prd(self):
        """Test analyzing sample PRD."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)

        assert data.project_name == "test-project"
        assert data.branch_name == "feature/test-branch"
        assert data.total_stories == 4
        assert data.complete_stories == 2
        assert data.running_stories == 0

    def test_analyze_prd_with_current_story(self):
        """Test analyzing PRD with current story."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD, current_story_id="TS-003")

        assert data.running_stories == 1
        assert data.current_story == "TS-003"

    def test_analyze_empty_prd(self):
        """Test analyzing empty PRD."""
        data = progress_dashboard.analyze_prd(EMPTY_PRD)

        assert data.total_stories == 0
        assert data.complete_stories == 0

    def test_stories_sorted_by_priority(self):
        """Test that stories are sorted by priority."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)

        priorities = [s.priority for s in data.stories]
        assert priorities == sorted(priorities)

    def test_analyze_large_prd(self):
        """Test analyzing large PRD."""
        data = progress_dashboard.analyze_prd(LARGE_PRD)

        assert data.total_stories == 20
        assert data.complete_stories == 10


# ============================================================================
# Test: Phase Progress
# ============================================================================

class TestPhaseProgress:
    """Tests for phase progress calculation."""

    def test_phase_progress_percent(self):
        """Test phase progress percentage calculation."""
        phase = progress_dashboard.PhaseProgress(
            name="implementation",
            stories_total=10,
            stories_complete=5
        )
        assert phase.progress_percent == 50.0

    def test_phase_progress_zero_total(self):
        """Test phase progress with zero total stories."""
        phase = progress_dashboard.PhaseProgress(
            name="implementation",
            stories_total=0,
            stories_complete=0
        )
        assert phase.progress_percent == 0.0

    def test_phase_is_complete(self):
        """Test phase completion detection."""
        complete_phase = progress_dashboard.PhaseProgress(
            name="planning",
            stories_total=1,
            stories_complete=1
        )
        incomplete_phase = progress_dashboard.PhaseProgress(
            name="implementation",
            stories_total=10,
            stories_complete=5
        )
        assert complete_phase.is_complete is True
        assert incomplete_phase.is_complete is False


# ============================================================================
# Test: Progress Bar Rendering
# ============================================================================

class TestProgressBarRendering:
    """Tests for progress bar rendering."""

    def test_progress_bar_empty(self):
        """Test rendering empty progress bar."""
        bar = progress_dashboard.render_progress_bar(0, width=10)
        assert bar == "[░░░░░░░░░░]"

    def test_progress_bar_full(self):
        """Test rendering full progress bar."""
        bar = progress_dashboard.render_progress_bar(100, width=10)
        assert bar == "[██████████]"

    def test_progress_bar_half(self):
        """Test rendering half-filled progress bar."""
        bar = progress_dashboard.render_progress_bar(50, width=10)
        assert bar == "[█████░░░░░]"

    def test_progress_bar_with_active(self):
        """Test rendering progress bar with active indicator."""
        bar = progress_dashboard.render_progress_bar(50, width=10, is_active=True)
        assert bar == "[█████▓░░░░]"

    def test_progress_bar_full_with_active(self):
        """Test that full bar doesn't show active indicator."""
        bar = progress_dashboard.render_progress_bar(100, width=10, is_active=True)
        assert bar == "[██████████]"


# ============================================================================
# Test: Dashboard Rendering
# ============================================================================

class TestDashboardRendering:
    """Tests for dashboard rendering."""

    def test_render_dashboard_contains_project_name(self):
        """Test that dashboard contains project name."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data)
        assert "test-project" in output

    def test_render_dashboard_contains_branch_name(self):
        """Test that dashboard contains branch name."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data)
        assert "feature/test-branch" in output

    def test_render_dashboard_contains_stories(self):
        """Test that dashboard contains story IDs."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data)
        assert "TS-001" in output
        assert "TS-002" in output

    def test_render_dashboard_no_color(self):
        """Test rendering dashboard without colors."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data, colors=progress_dashboard.NO_COLORS)
        # Should not contain ANSI escape codes
        assert "\033[" not in output

    def test_render_dashboard_with_colors(self):
        """Test rendering dashboard with colors."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data, colors=progress_dashboard.COLORS)
        # Should contain ANSI escape codes
        assert "\033[" in output

    def test_render_dashboard_max_stories(self):
        """Test limiting number of stories displayed."""
        data = progress_dashboard.analyze_prd(LARGE_PRD)
        output = progress_dashboard.render_dashboard(data, max_stories=5)
        # Should show "... and X more"
        assert "more" in output

    def test_render_dashboard_no_stories(self):
        """Test rendering dashboard without story list."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_dashboard(data, show_stories=False)
        # Story IDs should not appear
        assert "TS-001" not in output


# ============================================================================
# Test: Compact Rendering
# ============================================================================

class TestCompactRendering:
    """Tests for compact progress rendering."""

    def test_render_compact_contains_progress(self):
        """Test compact rendering contains progress counts."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.render_compact(data)
        assert "2/4" in output

    def test_render_compact_shows_current_story(self):
        """Test compact rendering shows current story."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD, current_story_id="TS-003")
        output = progress_dashboard.render_compact(data)
        assert "TS-003" in output

    def test_render_compact_shows_complete(self):
        """Test compact rendering shows COMPLETE when all done."""
        all_complete_prd = {
            "project": "test",
            "branchName": "main",
            "description": "",
            "userStories": [
                {"id": "US-1", "title": "Story 1", "priority": 1, "passes": True}
            ]
        }
        data = progress_dashboard.analyze_prd(all_complete_prd)
        output = progress_dashboard.render_compact(data)
        assert "COMPLETE" in output


# ============================================================================
# Test: JSON Output
# ============================================================================

class TestJSONOutput:
    """Tests for JSON output."""

    def test_json_output_valid(self):
        """Test that JSON output is valid JSON."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.to_json(data)
        parsed = json.loads(output)
        assert parsed["project_name"] == "test-project"

    def test_json_output_contains_summary(self):
        """Test that JSON output contains summary."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.to_json(data)
        parsed = json.loads(output)
        assert "summary" in parsed
        assert parsed["summary"]["total_stories"] == 4
        assert parsed["summary"]["complete_stories"] == 2

    def test_json_output_contains_phases(self):
        """Test that JSON output contains phases."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.to_json(data)
        parsed = json.loads(output)
        assert "phases" in parsed
        assert len(parsed["phases"]) > 0

    def test_json_output_contains_stories(self):
        """Test that JSON output contains stories."""
        data = progress_dashboard.analyze_prd(SAMPLE_PRD)
        output = progress_dashboard.to_json(data)
        parsed = json.loads(output)
        assert "stories" in parsed
        assert len(parsed["stories"]) == 4


# ============================================================================
# Test: Status Indicators
# ============================================================================

class TestStatusIndicators:
    """Tests for status indicator constants."""

    def test_status_indicators_defined(self):
        """Test that all status indicators are defined."""
        assert progress_dashboard.STATUS_COMPLETE == "✓"
        assert progress_dashboard.STATUS_RUNNING == "▶"
        assert progress_dashboard.STATUS_PENDING == "○"
        assert progress_dashboard.STATUS_FAILED == "✗"

    def test_progress_bar_chars_defined(self):
        """Test that progress bar characters are defined."""
        assert progress_dashboard.BAR_FILLED == "█"
        assert progress_dashboard.BAR_ACTIVE == "▓"
        assert progress_dashboard.BAR_EMPTY == "░"


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_prd_without_branch_name(self):
        """Test PRD without branch name."""
        prd = {
            "project": "test",
            "description": "",
            "userStories": []
        }
        data = progress_dashboard.analyze_prd(prd)
        assert data.branch_name == ""

    def test_prd_without_description(self):
        """Test PRD without description."""
        prd = {
            "project": "test",
            "branchName": "main",
            "userStories": []
        }
        data = progress_dashboard.analyze_prd(prd)
        assert data.project_name == "test"

    def test_story_with_very_long_title(self):
        """Test story with very long title gets truncated."""
        prd = {
            "project": "test",
            "branchName": "main",
            "description": "",
            "userStories": [
                {
                    "id": "US-1",
                    "title": "A" * 100,  # Very long title
                    "priority": 1,
                    "passes": False
                }
            ]
        }
        data = progress_dashboard.analyze_prd(prd)
        output = progress_dashboard.render_dashboard(data)
        # Title should be truncated with "..."
        assert "..." in output

    def test_all_stories_complete(self):
        """Test when all stories are complete."""
        prd = {
            "project": "test",
            "branchName": "main",
            "description": "",
            "userStories": [
                {"id": "US-1", "title": "Story 1", "priority": 1, "passes": True},
                {"id": "US-2", "title": "Story 2", "priority": 2, "passes": True},
            ]
        }
        data = progress_dashboard.analyze_prd(prd)
        assert data.complete_stories == 2
        assert data.total_stories == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
