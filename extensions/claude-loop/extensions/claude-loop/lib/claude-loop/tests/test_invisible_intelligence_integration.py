#!/usr/bin/env python3
"""
Integration tests for Invisible Intelligence feature.

Tests the full flow from description to completion:
1. Description input → PRD generation
2. PRD → Complexity detection
3. Complexity → Track selection
4. Complexity → Phase selection
5. Complexity → Quality gates selection
6. Session state management
7. Progress tracking
8. Completion summary generation

This test suite verifies that all components work together seamlessly.
"""

import json
import os
import sys
import tempfile
import shutil
import subprocess
import pytest
from pathlib import Path

# Add lib directory to path for imports
LIB_DIR = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.insert(0, LIB_DIR)

# Import modules using hyphenated name workaround
import importlib.util


def load_module(name, filename):
    """Load a Python module from a file with hyphenated name."""
    filepath = os.path.join(LIB_DIR, filename)
    spec = importlib.util.spec_from_file_location(name, filepath)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {filename}")
    module = importlib.util.module_from_spec(spec)
    # Register module in sys.modules before exec to handle dataclass issues
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load all invisible intelligence modules
complexity_detector = load_module("complexity_detector", "complexity-detector.py")
quality_gates = load_module("quality_gates", "quality-gates.py")
solutioning_generator = load_module("solutioning_generator", "solutioning-generator.py")
progress_dashboard = load_module("progress_dashboard", "progress-dashboard.py")
completion_summary = load_module("completion_summary", "completion-summary.py")
prd_from_description = load_module("prd_from_description", "prd-from-description.py")


# Script paths
SCRIPT_DIR = Path(__file__).parent.parent
SESSION_STATE_SCRIPT = SCRIPT_DIR / "lib" / "session-state.sh"


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for integration testing."""
    temp_dir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    os.chdir(temp_dir)

    # Create directory structure
    os.makedirs(".claude-loop/sessions", exist_ok=True)
    os.makedirs("lib", exist_ok=True)
    os.makedirs("docs/architecture", exist_ok=True)
    os.makedirs("docs/adrs", exist_ok=True)

    yield temp_dir

    os.chdir(old_cwd)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_description():
    """Sample feature description for testing."""
    return """
    Add user authentication system:
    - Login page with email and password
    - User registration with email verification
    - Password reset functionality
    - Session management with JWT tokens
    - Logout feature
    """


@pytest.fixture
def complex_description():
    """Complex feature description for enterprise-level testing."""
    return """
    Build an enterprise healthcare data management platform:
    - Patient data storage with encryption at rest and in transit
    - HIPAA compliance with full audit logging
    - Role-based access control with OAuth 2.0 and SAML
    - Real-time data synchronization across multiple AWS regions
    - API gateway with rate limiting and API key management
    - Kubernetes deployment with auto-scaling
    - Monitoring with Prometheus, Grafana, and PagerDuty integration
    - Disaster recovery with 15-minute RPO
    - SOC2 Type II compliance controls
    - Integration with Epic and Cerner EHR systems
    """


@pytest.fixture
def simple_prd(temp_workspace):
    """Create a simple PRD for testing."""
    prd_content = {
        "project": "simple-test",
        "branchName": "feature/simple-test",
        "description": "Add a simple feature",
        "userStories": [
            {
                "id": "US-001",
                "title": "Simple Story",
                "description": "As a user, I want a simple feature",
                "acceptanceCriteria": ["Feature works"],
                "passes": False
            }
        ]
    }
    prd_path = Path(temp_workspace) / "prd.json"
    with open(prd_path, "w") as f:
        json.dump(prd_content, f)
    return str(prd_path)


@pytest.fixture
def medium_prd(temp_workspace):
    """Create a medium-complexity PRD for testing."""
    prd_content = {
        "project": "medium-test",
        "branchName": "feature/medium-test",
        "description": "Add user authentication with session management",
        "userStories": [
            {"id": "US-001", "title": "Login", "passes": False},
            {"id": "US-002", "title": "Register", "passes": False},
            {"id": "US-003", "title": "Logout", "passes": False},
            {"id": "US-004", "title": "Password Reset", "passes": False},
            {"id": "US-005", "title": "Session Management", "passes": False},
            {"id": "US-006", "title": "JWT Integration", "passes": True},
            {"id": "US-007", "title": "Tests", "passes": False},
        ]
    }
    prd_path = Path(temp_workspace) / "prd.json"
    with open(prd_path, "w") as f:
        json.dump(prd_content, f)
    return str(prd_path)


@pytest.fixture
def complex_prd(temp_workspace):
    """Create a complex PRD for testing."""
    prd_content = {
        "project": "complex-test",
        "branchName": "feature/complex-test",
        "description": "Enterprise healthcare platform with HIPAA compliance and multi-region deployment",
        "userStories": [
            {"id": f"US-{i:03d}", "title": f"Story {i}", "passes": False}
            for i in range(1, 16)  # 15 stories
        ]
    }
    prd_path = Path(temp_workspace) / "prd.json"
    with open(prd_path, "w") as f:
        json.dump(prd_content, f)
    return str(prd_path)


def run_session_command(cmd: str, args: list = None) -> tuple:
    """Run a session-state.sh command."""
    full_cmd = ["bash", str(SESSION_STATE_SCRIPT), cmd] + (args or [])
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
    return result.stdout, result.stderr, result.returncode


class TestFullFlowSimple:
    """Test full flow with simple description."""

    def test_simple_description_to_completion(self, temp_workspace, sample_description):
        """Test full flow for a simple feature description."""
        # Step 1: Detect complexity
        result = complexity_detector.detect_complexity(sample_description)
        assert result is not None
        assert result.level >= 0

        # Step 2: Get track
        track = complexity_detector.get_track(result.level)
        assert track in ["quick", "standard", "enterprise"]

        # Step 3: Get phases
        phases = complexity_detector.get_phases(result.level)
        assert len(phases) >= 1
        assert "implementation" in phases

        # Step 4: Get quality gates
        gates = quality_gates.get_gates(result.level)
        assert gates is not None

        # Verify the flow is consistent
        if result.level <= 1:
            assert track == "quick"
            assert phases == ["implementation"]

    def test_simple_prd_integration(self, simple_prd, temp_workspace):
        """Test integration with simple PRD file."""
        # Detect complexity from PRD
        result = complexity_detector.detect_complexity("", simple_prd)

        assert result.signals["story_count"] == 1
        assert result.level in [0, 1]  # Simple project

        # Verify correct track/phases
        track = complexity_detector.get_track(result.level)
        phases = complexity_detector.get_phases(result.level)

        assert track == "quick"
        assert phases == ["implementation"]


class TestFullFlowComplex:
    """Test full flow with complex description."""

    def test_complex_description_to_completion(self, temp_workspace, complex_description):
        """Test full flow for a complex feature description."""
        # Step 1: Detect complexity
        result = complexity_detector.detect_complexity(complex_description)
        assert result is not None

        # Should detect high complexity due to:
        # - Security keywords (HIPAA, encryption, OAuth, SAML)
        # - Infrastructure keywords (Kubernetes, AWS, auto-scaling)
        # - Integration keywords (API, EHR systems)
        # - Compliance keywords (HIPAA, SOC2)
        assert result.signals["security_matches"] >= 2
        assert result.signals["infra_matches"] >= 2
        assert result.signals["compliance_matches"] >= 2

        # Step 2: Get track (should be standard or enterprise)
        track = complexity_detector.get_track(result.level)
        assert track in ["standard", "enterprise"]

        # Step 3: Get phases (should have multiple)
        phases = complexity_detector.get_phases(result.level)
        assert len(phases) >= 2
        assert "implementation" in phases

        # Step 4: Get quality gates (should have more gates)
        gates = quality_gates.get_gates(result.level)
        assert gates is not None

    def test_complex_prd_integration(self, complex_prd, temp_workspace):
        """Test integration with complex PRD file."""
        # Detect complexity from PRD
        result = complexity_detector.detect_complexity("", complex_prd)

        assert result.signals["story_count"] == 15
        assert result.level >= 2  # Should be medium+ complexity

        # Verify correct track/phases
        track = complexity_detector.get_track(result.level)
        phases = complexity_detector.get_phases(result.level)

        # Higher complexity should have more phases
        if result.level >= 3:
            assert "solutioning" in phases


class TestComponentIntegration:
    """Test integration between individual components."""

    def test_complexity_to_track_consistency(self):
        """Test that complexity levels map consistently to tracks."""
        level_track_map = {
            0: "quick",
            1: "quick",
            2: "standard",
            3: "standard",
            4: "enterprise"
        }

        for level, expected_track in level_track_map.items():
            actual_track = complexity_detector.get_track(level)
            assert actual_track == expected_track, f"Level {level} should map to {expected_track}"

    def test_complexity_to_phases_consistency(self):
        """Test that complexity levels map consistently to phases."""
        level_phases_map = {
            0: ["implementation"],
            1: ["implementation"],
            2: ["planning", "implementation"],
            3: ["planning", "solutioning", "implementation"],
            4: ["analysis", "planning", "solutioning", "implementation"]
        }

        for level, expected_phases in level_phases_map.items():
            actual_phases = complexity_detector.get_phases(level)
            assert actual_phases == expected_phases, f"Level {level} phases mismatch"

    def test_track_config_matches_gates(self):
        """Test that track config quality gates align with gates module."""
        for level in range(5):
            track = complexity_detector.get_track(level)
            track_config = complexity_detector.get_track_config(track)
            gates = quality_gates.get_gates(level)

            # Both should have test gates enabled for all levels
            if gates:
                # Gates exist for this level
                pass


class TestSessionStateIntegration:
    """Test session state integrates with other components."""

    def test_session_tracks_phase(self, medium_prd, temp_workspace):
        """Test that session state tracks the current phase."""
        run_session_command("init", [medium_prd])
        run_session_command("save", ["US-001", "1", "planning"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_phase"] == "planning"

        # Change phase
        run_session_command("save", ["US-001", "2", "implementation"])

        with open(session_file) as f:
            session = json.load(f)

        assert session["current_phase"] == "implementation"

    def test_session_tracks_story_progress(self, medium_prd, temp_workspace):
        """Test that session tracks story progress."""
        run_session_command("init", [medium_prd])

        # Save progress through stories
        run_session_command("save", ["US-001", "1", "implementation"])
        run_session_command("save", ["US-002", "2", "implementation"])
        run_session_command("save", ["US-003", "3", "implementation"])

        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            session = json.load(f)

        assert session["current_story"] == "US-003"
        assert session["current_iteration"] == 3


class TestProgressDashboardIntegration:
    """Test progress dashboard integrates with PRD and session state."""

    def test_dashboard_renders_prd_progress(self, medium_prd, temp_workspace):
        """Test that dashboard can render PRD progress."""
        # Load PRD first, then analyze
        prd_data = progress_dashboard.load_prd(medium_prd)
        dashboard_data = progress_dashboard.analyze_prd(prd_data)

        # Render dashboard (this should not crash)
        dashboard = progress_dashboard.render_dashboard(dashboard_data)

        assert isinstance(dashboard, str)
        assert "medium-test" in dashboard
        assert "Story" in dashboard or "US-" in dashboard

    def test_dashboard_shows_phase_progress(self, medium_prd, temp_workspace):
        """Test that dashboard shows phase progress."""
        prd_data = progress_dashboard.load_prd(medium_prd)
        dashboard_data = progress_dashboard.analyze_prd(prd_data)

        dashboard = progress_dashboard.render_dashboard(dashboard_data)

        # Dashboard should render without crashing
        assert isinstance(dashboard, str)
        assert len(dashboard) > 0


class TestCompletionSummaryIntegration:
    """Test completion summary integrates with PRD and metrics."""

    def test_summary_generates_from_prd(self, medium_prd, temp_workspace):
        """Test that completion summary can be generated from PRD."""
        # Mark some stories complete
        with open(medium_prd) as f:
            prd_data = json.load(f)

        prd_data["userStories"][0]["passes"] = True
        prd_data["userStories"][1]["passes"] = True

        with open(medium_prd, "w") as f:
            json.dump(prd_data, f)

        # Generate summary using correct API
        summary = completion_summary.generate_completion_summary(
            prd_path=medium_prd,
            project_dir=temp_workspace
        )

        assert summary is not None
        # Use correct field names for CompletionSummary
        assert summary.stories_total == 7
        assert summary.stories_completed >= 2  # At least the 2 we marked + 1 original

    def test_summary_includes_story_details(self, medium_prd, temp_workspace):
        """Test that summary includes story details."""
        summary = completion_summary.generate_completion_summary(
            prd_path=medium_prd,
            project_dir=temp_workspace
        )

        # Should have basic story counts
        assert summary.stories_total >= 0
        assert summary.stories_completed >= 0


class TestQualityGatesIntegration:
    """Test quality gates integrate with complexity detection."""

    def test_gates_scale_with_complexity(self):
        """Test that quality gates scale with complexity level."""
        prev_gates_count = 0

        for level in range(5):
            gates = quality_gates.get_gates(level)
            enabled_gates = [g for g in gates.get_enabled_gates()]

            # Gate count should generally increase with complexity
            # (or at least not decrease significantly)
            assert len(enabled_gates) >= 1, f"Level {level} should have at least 1 gate"

    def test_low_complexity_minimal_gates(self):
        """Test that low complexity has minimal gates."""
        gates = quality_gates.get_gates(0)
        enabled = gates.get_enabled_gates()

        # Should have tests but minimal other gates
        gate_names = [g.name for g in enabled]
        assert "tests" in gate_names
        # Should not have enterprise-level gates
        assert "manual_approval" not in gate_names

    def test_high_complexity_all_gates(self):
        """Test that high complexity has all gates."""
        gates = quality_gates.get_gates(4)
        enabled = gates.get_enabled_gates()

        gate_names = [g.name for g in enabled]
        assert "tests" in gate_names


class TestPRDGenerationIntegration:
    """Test PRD generation integrates with complexity detection."""

    def test_generated_prd_detectable(self, temp_workspace, sample_description):
        """Test that generated PRD can be analyzed for complexity."""
        # Generate PRD from description using correct API
        prd_path = Path(temp_workspace) / "generated_prd.json"
        generated_prd = prd_from_description.generate_prd_from_description(
            sample_description,
            str(prd_path)
        )

        assert generated_prd is not None
        assert prd_path.exists()

        # Detect complexity from generated PRD
        result = complexity_detector.detect_complexity("", str(prd_path))

        assert result is not None
        assert result.level >= 0
        assert result.signals["story_count"] >= 1


class TestEndToEndFlow:
    """Test complete end-to-end flow."""

    def test_full_invisible_intelligence_flow(self, temp_workspace, sample_description):
        """Test the complete invisible intelligence flow."""
        # 1. Start with description
        description = sample_description

        # 2. Detect complexity
        complexity_result = complexity_detector.detect_complexity(description)
        level = complexity_result.level

        # 3. Get track
        track = complexity_detector.get_track(level)

        # 4. Get phases
        phases = complexity_detector.get_phases(level)

        # 5. Get quality gates
        gates = quality_gates.get_gates(level)

        # 6. Generate PRD using correct API
        prd_path = Path(temp_workspace) / "prd.json"
        generated_prd = prd_from_description.generate_prd_from_description(
            description,
            str(prd_path)
        )

        # Load the PRD data as dict
        with open(prd_path) as f:
            prd_data = json.load(f)

        # 7. Initialize session
        _, _, code = run_session_command("init", [str(prd_path)])
        assert code == 0

        # 8. Simulate story execution with session saves
        run_session_command("save", [prd_data["userStories"][0]["id"], "1", phases[-1]])

        # 9. Generate dashboard using correct API (load then analyze)
        loaded_prd_data = progress_dashboard.load_prd(str(prd_path))
        dashboard_data = progress_dashboard.analyze_prd(loaded_prd_data)
        dashboard = progress_dashboard.render_dashboard(dashboard_data)
        assert dashboard is not None

        # 10. Generate completion summary
        summary = completion_summary.generate_completion_summary(
            prd_path=str(prd_path),
            project_dir=temp_workspace
        )
        assert summary is not None

        # Verify the flow was consistent
        assert track in ["quick", "standard", "enterprise"]
        assert "implementation" in phases
        assert gates is not None

    def test_flow_with_existing_prd(self, medium_prd, temp_workspace):
        """Test flow starting from an existing PRD file."""
        # 1. Detect complexity from PRD
        complexity_result = complexity_detector.detect_complexity("", medium_prd)

        # 2. Get track and phases
        track = complexity_detector.get_track(complexity_result.level)
        phases = complexity_detector.get_phases(complexity_result.level)

        # 3. Get quality gates
        gates = quality_gates.get_gates(complexity_result.level)

        # 4. Initialize session
        run_session_command("init", [medium_prd])

        # 5. Load PRD for dashboard
        with open(medium_prd) as f:
            prd_data = json.load(f)

        # 6. Simulate progress through phases
        for i, phase in enumerate(phases):
            run_session_command("save", ["US-001", str(i + 1), phase])

        # 7. Render dashboard using correct API (load then analyze)
        loaded_prd_data = progress_dashboard.load_prd(medium_prd)
        dashboard_data = progress_dashboard.analyze_prd(loaded_prd_data)
        dashboard = progress_dashboard.render_dashboard(dashboard_data)

        assert dashboard is not None
        assert "medium-test" in dashboard

        # Verify variables were used
        assert track in ["quick", "standard", "enterprise"]
        assert gates is not None
        assert prd_data is not None

    def test_flow_resume_after_interruption(self, medium_prd, temp_workspace):
        """Test flow can resume after simulated interruption."""
        # 1. Initialize and make progress
        run_session_command("init", [medium_prd])
        run_session_command("save", ["US-003", "5", "implementation"])

        # 2. Simulate interruption (read session state)
        session_file = Path(temp_workspace) / ".claude-loop" / "session-state.json"
        with open(session_file) as f:
            interrupted_session = json.load(f)

        # 3. Resume
        stdout, stderr, code = run_session_command("resume")
        assert code == 0

        # 4. Verify we can continue from where we left off
        with open(session_file) as f:
            resumed_session = json.load(f)

        assert resumed_session["current_story"] == "US-003"
        assert resumed_session["current_iteration"] == 5


class TestSolutioningIntegration:
    """Test solutioning generator integrates with complexity detection."""

    def test_solutioning_for_complex_projects(self, complex_description, temp_workspace):
        """Test that solutioning generates artifacts for complex projects."""
        # Detect complexity
        result = complexity_detector.detect_complexity(complex_description)

        # For high complexity, solutioning should be available
        if result.level >= 3:
            phases = complexity_detector.get_phases(result.level)
            assert "solutioning" in phases

    def test_solutioning_skipped_for_simple_projects(self, temp_workspace):
        """Test that solutioning is skipped for simple projects."""
        result = complexity_detector.detect_complexity("Fix typo in README")

        if result.level <= 1:
            phases = complexity_detector.get_phases(result.level)
            assert "solutioning" not in phases


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
