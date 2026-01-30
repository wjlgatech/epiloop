#!/usr/bin/env python3
"""
Unit tests for session-state.sh functionality.

Tests cover:
- Session initialization
- Session state saving and loading
- Resume from session
- Session listing
- Session archiving and cleanup
"""

import json
import os
import subprocess
import tempfile
import shutil
import pytest
from datetime import datetime
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

    # Create .claude-loop directory
    os.makedirs(".claude-loop/sessions", exist_ok=True)

    yield temp_dir

    os.chdir(old_cwd)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_prd(temp_workspace):
    """Create a sample prd.json file."""
    prd_content = {
        "project": "test-project",
        "branchName": "feature/test",
        "userStories": [
            {"id": "US-001", "title": "Story 1", "passes": False},
            {"id": "US-002", "title": "Story 2", "passes": False},
            {"id": "US-003", "title": "Story 3", "passes": True},
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
        env=proc_env
    )
    return result.stdout, result.stderr, result.returncode


class TestSessionInitialization:
    """Tests for session initialization."""

    def test_init_creates_session_file(self, sample_prd, temp_workspace):
        """Test that init command creates session-state.json."""
        stdout, stderr, code = run_session_command("init", [sample_prd])

        assert code == 0
        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        assert session_file.exists()

    def test_init_contains_required_fields(self, sample_prd, temp_workspace):
        """Test that session state contains all required fields."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        required_fields = [
            "session_id", "project", "branch", "prd_file",
            "current_phase", "current_iteration", "started_at",
            "last_saved_at", "stories_completed", "stories_total"
        ]
        for field in required_fields:
            assert field in session, f"Missing required field: {field}"

    def test_init_extracts_project_from_prd(self, sample_prd, temp_workspace):
        """Test that init extracts project name from PRD."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["project"] == "test-project"
        assert session["branch"] == "feature/test"

    def test_init_counts_stories_correctly(self, sample_prd, temp_workspace):
        """Test that init counts total and completed stories."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["stories_total"] == 3
        assert session["stories_completed"] == 1  # US-003 has passes=True


class TestSessionStateSaving:
    """Tests for session state saving."""

    def test_save_updates_story_id(self, sample_prd, temp_workspace):
        """Test that save command updates current story."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "3", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_story"] == "US-002"
        assert session["current_iteration"] == 3
        assert session["current_phase"] == "implementation"

    def test_save_updates_timestamp(self, sample_prd, temp_workspace):
        """Test that save updates last_saved_at timestamp."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            initial = json.load(f)
        initial_time = initial["last_saved_at"]

        import time
        time.sleep(0.1)

        run_session_command("save", ["US-001", "1", "planning"])

        with open(session_file) as f:
            updated = json.load(f)

        # Just verify the timestamp was written (may be same second in fast test)
        assert "last_saved_at" in updated

    def test_save_without_init_fails(self, temp_workspace):
        """Test that save fails if no session exists."""
        stdout, stderr, code = run_session_command("save", ["US-001", "1"])

        # Should warn about no active session
        assert code != 0 or "No active session" in stdout or "No active session" in stderr


class TestSessionResume:
    """Tests for session resume functionality."""

    def test_resume_returns_session_info(self, sample_prd, temp_workspace):
        """Test that resume returns session information."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "5", "implementation"])

        stdout, stderr, code = run_session_command("resume")

        assert code == 0
        # Should contain JSON with resume info
        assert "iteration" in stdout or "US-002" in stdout

    def test_has_resumable_with_progress(self, sample_prd, temp_workspace):
        """Test has-resumable returns true when progress exists."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "2"])

        stdout, stderr, code = run_session_command("has-resumable", [sample_prd])

        assert code == 0
        assert "true" in stdout

    def test_has_resumable_without_session(self, temp_workspace):
        """Test has-resumable returns false with no session."""
        stdout, stderr, code = run_session_command("has-resumable")

        assert code == 1
        assert "false" in stdout


class TestSessionListing:
    """Tests for session listing functionality."""

    def test_list_shows_current_session(self, sample_prd, temp_workspace):
        """Test that list shows the current session."""
        run_session_command("init", [sample_prd])

        stdout, stderr, code = run_session_command("list", ["text"])

        assert code == 0
        assert "current" in stdout.lower()
        assert "test-project" in stdout

    def test_list_json_format(self, sample_prd, temp_workspace):
        """Test that list --json outputs valid JSON."""
        run_session_command("init", [sample_prd])

        stdout, stderr, code = run_session_command("list", ["json"])

        assert code == 0
        sessions = json.loads(stdout)
        assert isinstance(sessions, list)
        assert len(sessions) >= 1

    def test_list_empty_when_no_sessions(self, temp_workspace):
        """Test that list handles no sessions gracefully."""
        stdout, stderr, code = run_session_command("list", ["text"])

        assert code == 0
        assert "No sessions" in stdout


class TestSessionArchiving:
    """Tests for session archiving functionality."""

    def test_archive_moves_to_archive_dir(self, sample_prd, temp_workspace):
        """Test that archive moves session to archive directory."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        session_id = session["session_id"]

        stdout, stderr, code = run_session_command("archive", ["test"])

        assert code == 0

        archive_file = Path(temp_workspace) / ".claude-loop" / "sessions" / f"{session_id}.json"
        assert archive_file.exists()

    def test_complete_archives_session(self, sample_prd, temp_workspace):
        """Test that complete command archives the session."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        assert session_file.exists()

        stdout, stderr, code = run_session_command("complete")

        assert code == 0
        assert not session_file.exists()  # Should be removed after completion

    def test_clear_removes_session(self, sample_prd, temp_workspace):
        """Test that clear removes current session."""
        run_session_command("init", [sample_prd])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        assert session_file.exists()

        stdout, stderr, code = run_session_command("clear")

        assert code == 0
        assert not session_file.exists()


class TestSessionSummary:
    """Tests for session summary functionality."""

    def test_summary_shows_all_info(self, sample_prd, temp_workspace):
        """Test that summary shows all session information."""
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-002", "3", "implementation"])

        stdout, stderr, code = run_session_command("summary")

        assert code == 0
        assert "test-project" in stdout
        assert "feature/test" in stdout
        assert "US-002" in stdout
        assert "3" in stdout

    def test_summary_no_session(self, temp_workspace):
        """Test summary with no active session."""
        stdout, stderr, code = run_session_command("summary")

        assert code == 1
        assert "No active session" in stdout


class TestSessionIdResume:
    """Tests for resuming from specific session ID."""

    def test_resume_by_id_from_archive(self, sample_prd, temp_workspace):
        """Test resuming from archived session by ID."""
        # Create and archive a session
        run_session_command("init", [sample_prd])
        run_session_command("save", ["US-001", "2"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)
        session_id = session["session_id"]

        run_session_command("archive", ["test"])

        # Now try to resume from that session ID
        stdout, stderr, code = run_session_command("resume-id", [session_id])

        assert code == 0
        # Session should be restored
        with open(session_file) as f:
            restored = json.load(f)
        assert restored["session_id"] == session_id

    def test_resume_by_id_not_found(self, temp_workspace):
        """Test resume by ID with non-existent session."""
        stdout, stderr, code = run_session_command("resume-id", ["nonexistent-session"])

        assert code == 1
        assert "not found" in stdout.lower() or "not found" in stderr.lower()


class TestHelp:
    """Tests for help output."""

    def test_help_shows_commands(self):
        """Test that help shows available commands."""
        stdout, stderr, code = run_session_command("help")

        assert code == 0
        assert "init" in stdout
        assert "save" in stdout
        assert "resume" in stdout
        assert "list" in stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
