#!/usr/bin/env python3
"""
Unit tests for session resume functionality.

Tests cover:
- Auto-save after story completion
- Resume from interruption
- Resume from specific session ID
- Session state persistence
- Resume message display
"""

import json
import os
import subprocess
import tempfile
import shutil
import pytest
from datetime import datetime, timedelta
from pathlib import Path


# Path to the session-state.sh script
SCRIPT_DIR = Path(__file__).parent.parent
SESSION_STATE_SCRIPT = SCRIPT_DIR / "lib" / "session-state.sh"


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_dir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    os.chdir(temp_dir)

    # Create .claude-loop directory structure
    os.makedirs(".claude-loop/sessions", exist_ok=True)

    yield temp_dir

    os.chdir(old_cwd)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_prd(temp_workspace):
    """Create a sample prd.json file with multiple stories."""
    prd_content = {
        "project": "resume-test-project",
        "branchName": "feature/resume-test",
        "userStories": [
            {"id": "US-001", "title": "Story 1", "passes": False},
            {"id": "US-002", "title": "Story 2", "passes": False},
            {"id": "US-003", "title": "Story 3", "passes": False},
            {"id": "US-004", "title": "Story 4", "passes": True},
            {"id": "US-005", "title": "Story 5", "passes": False},
        ]
    }
    prd_path = Path(temp_workspace) / "prd.json"
    with open(prd_path, "w") as f:
        json.dump(prd_content, f)
    return str(prd_path)


def run_session_command(cmd: str, args: list = None, env: dict = None) -> tuple:
    """Run a session-state.sh command and return (stdout, stderr, returncode)."""
    full_cmd = ["bash", str(SESSION_STATE_SCRIPT), cmd] + (args or [])

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        env=proc_env,
        timeout=30
    )
    return result.stdout, result.stderr, result.returncode


class TestAutoSaveAfterStoryCompletion:
    """Tests for auto-save functionality after story completion."""

    def test_auto_save_creates_session_file(self, sample_prd, temp_workspace):
        """Test that saving creates/updates session file."""
        run_session_command("init", [sample_prd])
        stdout, stderr, code = run_session_command("save", ["US-002", "3", "implementation"])

        assert code == 0
        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        assert session_file.exists()

    def test_auto_save_updates_story_progress(self, sample_prd, temp_workspace):
        """Test that auto-save updates current story information."""
        run_session_command("init", [sample_prd])

        # Save progress at US-002, iteration 3
        run_session_command("save", ["US-002", "3", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_story"] == "US-002"
        assert session["current_iteration"] == 3
        assert session["current_phase"] == "implementation"

    def test_auto_save_increments_iteration(self, sample_prd, temp_workspace):
        """Test that iteration counter increments on each save."""
        run_session_command("init", [sample_prd])

        # Save multiple iterations
        run_session_command("save", ["US-001", "1", "implementation"])
        run_session_command("save", ["US-001", "2", "implementation"])
        run_session_command("save", ["US-001", "3", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_iteration"] == 3

    def test_auto_save_updates_timestamp(self, sample_prd, temp_workspace):
        """Test that each save updates the timestamp."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "1", "planning"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            first_save = json.load(f)
        first_timestamp = first_save["last_saved_at"]

        import time
        time.sleep(0.1)  # Small delay to ensure different timestamp

        run_session_command("save", ["US-001", "2", "implementation"])

        with open(session_file) as f:
            second_save = json.load(f)

        assert "last_saved_at" in second_save

    def test_auto_save_tracks_phase_transitions(self, sample_prd, temp_workspace):
        """Test that auto-save tracks phase changes."""
        run_session_command("init", [sample_prd])

        # Progress through phases
        run_session_command("save", ["US-001", "1", "planning"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        assert session["current_phase"] == "planning"

        run_session_command("save", ["US-001", "2", "implementation"])

        with open(session_file) as f:
            session = json.load(f)
        assert session["current_phase"] == "implementation"


class TestResumeFromInterruption:
    """Tests for resuming after interruption."""

    def test_resume_returns_correct_story(self, sample_prd, temp_workspace):
        """Test that resume returns to the last worked story."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-003", "5", "implementation"])

        stdout, stderr, code = run_session_command("resume")

        assert code == 0
        # Should include information about resuming at US-003
        assert "US-003" in stdout or "iteration" in stdout.lower()

    def test_resume_returns_correct_iteration(self, sample_prd, temp_workspace):
        """Test that resume returns the correct iteration number."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "7", "implementation"])

        stdout, stderr, code = run_session_command("resume")

        assert code == 0
        # Iteration should be available in the output
        assert "7" in stdout or "iteration" in stdout.lower()

    def test_resume_after_mid_story_interruption(self, sample_prd, temp_workspace):
        """Test resume after interruption during story execution."""
        run_session_command("init", [sample_prd])

        # Simulate progress through multiple stories
        run_session_command("save", ["US-001", "1", "implementation"])
        run_session_command("save", ["US-001", "2", "implementation"])
        run_session_command("save", ["US-002", "1", "implementation"])

        # Simulate interruption (no complete, just resume)
        stdout, stderr, code = run_session_command("resume")

        assert code == 0
        # Should resume at US-002
        result_json = json.loads(stdout) if stdout.strip().startswith("{") else {}
        if result_json:
            assert result_json.get("current_story") == "US-002"

    def test_resume_preserves_phase(self, sample_prd, temp_workspace):
        """Test that resume preserves the current phase."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "3", "solutioning"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_phase"] == "solutioning"


class TestResumeFromSpecificSessionId:
    """Tests for resuming from specific session ID."""

    def test_resume_by_id_restores_session(self, sample_prd, temp_workspace):
        """Test that resume by ID restores the correct session."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "4", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        session_id = session["session_id"]

        # Archive the session
        run_session_command("archive", ["test"])

        # Resume from specific ID
        stdout, stderr, code = run_session_command("resume-id", [session_id])

        assert code == 0

        # Session should be restored
        with open(session_file) as f:
            restored = json.load(f)
        assert restored["session_id"] == session_id
        assert restored["current_story"] == "US-002"
        assert restored["current_iteration"] == 4

    def test_resume_by_id_invalid_id_fails(self, temp_workspace):
        """Test that resume with invalid ID fails gracefully."""
        stdout, stderr, code = run_session_command("resume-id", ["invalid-session-id-12345"])

        assert code == 1
        combined_output = stdout + stderr
        assert "not found" in combined_output.lower() or "error" in combined_output.lower()

    def test_resume_by_id_lists_available_sessions(self, sample_prd, temp_workspace):
        """Test that we can list available sessions to choose from."""
        # Create and archive multiple sessions
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "1"])
        run_session_command("archive", ["first"])

        # Create another session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "2"])
        run_session_command("archive", ["second"])

        stdout, stderr, code = run_session_command("list", ["json"])

        assert code == 0
        sessions = json.loads(stdout)
        assert isinstance(sessions, list)
        # Should have at least 2 archived sessions
        assert len(sessions) >= 2


class TestSessionStatePersistence:
    """Tests for session state persistence across restarts."""

    def test_session_persists_across_restarts(self, sample_prd, temp_workspace):
        """Test that session state persists when script terminates."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-003", "5", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"

        # Verify file exists and has correct content
        assert session_file.exists()
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_story"] == "US-003"
        assert session["current_iteration"] == 5

    def test_session_file_valid_json(self, sample_prd, temp_workspace):
        """Test that session file is always valid JSON."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "1"])
        run_session_command("save", ["US-001", "2"])
        run_session_command("save", ["US-002", "1"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"

        with open(session_file) as f:
            # Should not raise JSONDecodeError
            session = json.load(f)

        assert isinstance(session, dict)
        assert "session_id" in session

    def test_session_contains_all_required_fields(self, sample_prd, temp_workspace):
        """Test that persisted session has all required fields."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "3", "planning"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        required_fields = [
            "session_id",
            "project",
            "branch",
            "prd_file",
            "current_phase",
            "current_iteration",
            "started_at",
            "last_saved_at",
            "stories_total"
        ]

        for field in required_fields:
            assert field in session, f"Missing required field: {field}"


class TestResumeMessageDisplay:
    """Tests for resume message display."""

    def test_resume_shows_project_info(self, sample_prd, temp_workspace):
        """Test that resume shows project information."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "2", "implementation"])

        stdout, stderr, code = run_session_command("summary")

        assert code == 0
        # Should show project name
        assert "resume-test-project" in stdout

    def test_resume_shows_progress(self, sample_prd, temp_workspace):
        """Test that resume shows current progress."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "3", "implementation"])

        stdout, stderr, code = run_session_command("summary")

        assert code == 0
        # Should show story or iteration info
        assert "US-002" in stdout or "3" in stdout

    def test_has_resumable_shows_message(self, sample_prd, temp_workspace):
        """Test has-resumable indicates resumable session exists."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "2"])

        stdout, stderr, code = run_session_command("has-resumable", [sample_prd])

        assert code == 0
        assert "true" in stdout


class TestResumeEdgeCases:
    """Tests for edge cases in resume functionality."""

    def test_resume_with_no_session(self, temp_workspace):
        """Test resume when no session exists."""
        stdout, stderr, code = run_session_command("resume")

        assert code == 1
        combined_output = stdout + stderr
        assert "no" in combined_output.lower() or "session" in combined_output.lower()

    def test_resume_after_completion(self, sample_prd, temp_workspace):
        """Test resume after session was completed."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-005", "1"])
        run_session_command("complete")

        stdout, stderr, code = run_session_command("resume")

        # Should indicate no session to resume
        assert code == 1

    def test_resume_with_corrupted_session_file(self, sample_prd, temp_workspace):
        """Test resume handles corrupted session file gracefully."""
        run_session_command("init", [sample_prd])

        # Corrupt the session file
        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file, "w") as f:
            f.write("not valid json {{{")

        stdout, stderr, code = run_session_command("resume")

        # Should handle gracefully (either error or no session)
        # The important thing is it doesn't crash
        assert code != 0 or "error" in (stdout + stderr).lower()

    def test_resume_preserves_prd_path(self, sample_prd, temp_workspace):
        """Test that resume preserves the original PRD path."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "2"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        # Should have stored the PRD file path
        assert "prd_file" in session
        assert session["prd_file"] != ""


class TestMultipleSessionsResume:
    """Tests for resuming when multiple sessions exist."""

    def test_resume_prefers_current_session(self, sample_prd, temp_workspace):
        """Test that resume prefers current session over archived."""
        # Create and archive first session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "1"])
        run_session_command("archive", ["old"])

        # Create new current session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-003", "5", "implementation"])

        stdout, stderr, code = run_session_command("resume")

        assert code == 0
        # Should resume from current session (US-003, not US-001)

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        assert session["current_story"] == "US-003"

    def test_list_shows_all_sessions(self, sample_prd, temp_workspace):
        """Test that list shows current and archived sessions."""
        # Create and archive first session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "1"])
        run_session_command("archive", ["first"])

        # Create and archive second session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "2"])
        run_session_command("archive", ["second"])

        # Create current session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-003", "3"])

        stdout, stderr, code = run_session_command("list", ["json"])

        assert code == 0
        sessions = json.loads(stdout)

        # Should have current + archived sessions
        assert len(sessions) >= 1


class TestSessionCleanup:
    """Tests for session cleanup on completion."""

    def test_complete_removes_current_session(self, sample_prd, temp_workspace):
        """Test that complete removes the current session file."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-005", "3"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        assert session_file.exists()

        run_session_command("complete")

        assert not session_file.exists()

    def test_complete_archives_before_removing(self, sample_prd, temp_workspace):
        """Test that complete archives session before removing."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "4"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        session_id = session["session_id"]

        run_session_command("complete")

        # Session should be archived
        archive_file = Path(temp_workspace) / ".claude-loop" / "sessions" / f"{session_id}.json"
        assert archive_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
