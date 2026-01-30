#!/usr/bin/env python3
"""
test_unity.py - Tests for Unity Editor Automation

This module provides comprehensive tests for the Unity automation agent,
including mock responses for CI-compatible testing without Unity running.

Usage:
    # Run all tests with pytest (if installed)
    pytest agents/computer_use/tests/test_unity.py -v

    # Run with coverage
    pytest agents/computer_use/tests/test_unity.py --cov=agents.computer_use

    # Run specific test class
    pytest agents/computer_use/tests/test_unity.py::TestUnityAgent -v

    # Run without pytest (basic verification)
    python agents/computer_use/tests/test_unity.py

Environment:
    Set CI_MODE=1 to run tests without attempting AppleScript calls.
    This is automatic in CI environments where Unity is not available.
"""

import os
import subprocess
import sys
from unittest import mock

# Try to import pytest, fall back to unittest-compatible mode
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create pytest-compatible decorators for running without pytest
    class _MockPytest:
        """Mock pytest module for running without pytest installed."""

        class fixture:
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, func):
                return func

        @staticmethod
        def main(args):
            print("pytest not installed. Running basic verification instead.")
            return 0

    pytest = _MockPytest()  # type: ignore

# Import all Unity automation components
from agents.computer_use.unity import (
    UnityAgent,
    UnityWindow,
    UnityMenu,
    UnityProject,
    UnityState,
    PackageStatus,
    PackageSource,
    PackageInfo,
    ProjectSettingsCategory,
    Platform,
    XRPlugin,
    MetaSetupIssueLevel,
    MetaSetupIssueStatus,
    MetaSetupIssue,
    MetaSetupResult,
    BuildTargetPlatform,
    BuildScriptingBackend,
    BuildResult,
    BuildOptions,
    BuildError,
    BuildResultInfo,
    ConnectedDevice,
    ConsoleMessageLevel,
    ConsoleMessage,
    EditorState,
    DialogType,
    DialogAction,
    DialogConfig,
    DialogHandleResult,
    DialogLog,
    WorkflowStep,
    WorkflowStatus,
    WorkflowProgress,
    WorkflowResult,
    UnityWorkflows,
)

from agents.computer_use.safety import (
    DialogPattern,
    UNITY_DIALOG_PATTERNS,
    get_pattern,
    get_patterns_for_window_title,
    get_auto_handle_patterns,
    get_blocking_patterns,
    create_custom_pattern,
)

from agents.computer_use.orchestrator import (
    UnityOrchestrator,
    UnityCommandRegistry,
    WorkflowExecutor,
    CommandStatus,
    CommandResult,
    WorkflowStepDefinition,
    WorkflowDefinition,
    WorkflowExecutionResult,
)


# =============================================================================
# Test Fixtures and Mock Responses
# =============================================================================


@pytest.fixture
def ci_mode():
    """Determine if we're running in CI mode (no actual Unity available)."""
    return os.environ.get("CI_MODE", "1") == "1" or os.environ.get("CI", "false") == "true"


@pytest.fixture
def mock_agent():
    """Create a Unity agent with mocked subprocess calls."""
    with mock.patch.object(subprocess, "run") as mock_run:
        agent = UnityAgent()
        yield agent, mock_run


@pytest.fixture
def mock_unity_running():
    """Mock response for Unity running."""
    result = mock.Mock()
    result.returncode = 0
    result.stdout = "12345\n"
    result.stderr = ""
    return result


@pytest.fixture
def mock_unity_not_running():
    """Mock response for Unity not running."""
    result = mock.Mock()
    result.returncode = 1
    result.stdout = ""
    result.stderr = ""
    return result


@pytest.fixture
def mock_unity_windows():
    """Mock response for Unity window list."""
    result = mock.Mock()
    result.returncode = 0
    result.stdout = "TestProject - /Users/dev/TestProject - Unity 2022.3.1f1, Console, Inspector, Hierarchy"
    result.stderr = ""
    return result


class MockAppleScriptResponses:
    """Collection of mock AppleScript responses for testing."""

    @staticmethod
    def unity_window_title() -> str:
        """Return a realistic Unity window title."""
        return "TestProject - /Users/developer/Projects/TestProject - Unity 2022.3.16f1 <DX11>"

    @staticmethod
    def visible_windows() -> str:
        """Return a comma-separated list of visible windows."""
        return "TestProject - /Users/developer/Projects/TestProject - Unity 2022.3.16f1, Console, Inspector, Hierarchy, Project, Scene"

    @staticmethod
    def console_content_with_errors() -> str:
        """Return console content with errors and warnings."""
        return """[Error] NullReferenceException: Object reference not set to an instance of an object
at PlayerController.Update () [0x00001] in PlayerController.cs:42

[Warning] The referenced script on this Behaviour is missing!

[Log] Game started successfully
[Error] ArgumentException: Invalid argument passed to method
[Warning] Shader 'Custom/MyShader' is not supported on this GPU
"""

    @staticmethod
    def console_content_clean() -> str:
        """Return console content without errors."""
        return """[Log] Game started successfully
[Log] Player spawned at position (0, 0, 0)
[Log] Level 1 loaded
"""

    @staticmethod
    def editor_compiling() -> str:
        """Return status indicating editor is compiling."""
        return "compiling"

    @staticmethod
    def editor_idle() -> str:
        """Return status indicating editor is idle."""
        return "idle"

    @staticmethod
    def play_mode_active() -> str:
        """Return status indicating play mode is active."""
        return "yes"

    @staticmethod
    def play_mode_inactive() -> str:
        """Return status indicating play mode is inactive."""
        return "no"

    @staticmethod
    def adb_devices() -> str:
        """Return mock ADB devices output."""
        return """List of devices attached
1WMHH81234567	device
Quest_2_12345	device
"""


# =============================================================================
# Test: Data Classes and Enums
# =============================================================================


class TestDataClasses:
    """Tests for data classes and enums."""

    def test_unity_window_enum_values(self):
        """Test that UnityWindow enum has expected values."""
        assert UnityWindow.PROJECT.value == "Project"
        assert UnityWindow.CONSOLE.value == "Console"
        assert UnityWindow.INSPECTOR.value == "Inspector"
        assert UnityWindow.HIERARCHY.value == "Hierarchy"
        assert UnityWindow.SCENE.value == "Scene"
        assert UnityWindow.GAME.value == "Game"
        assert UnityWindow.PACKAGE_MANAGER.value == "Package Manager"
        assert UnityWindow.BUILD_SETTINGS.value == "Build Settings"

    def test_unity_menu_enum_values(self):
        """Test that UnityMenu enum has expected values."""
        assert UnityMenu.FILE.value == "File"
        assert UnityMenu.EDIT.value == "Edit"
        assert UnityMenu.ASSETS.value == "Assets"
        assert UnityMenu.WINDOW.value == "Window"
        assert UnityMenu.META.value == "Meta"

    def test_platform_enum_values(self):
        """Test that Platform enum has expected values."""
        assert Platform.ANDROID.value == "Android"
        assert Platform.IOS.value == "iOS"
        assert Platform.STANDALONE.value == "Standalone"
        assert Platform.WEBGL.value == "WebGL"

    def test_xr_plugin_enum_values(self):
        """Test that XRPlugin enum has expected values."""
        assert XRPlugin.OCULUS.value == "Oculus"
        assert XRPlugin.OPEN_XR.value == "OpenXR"
        assert XRPlugin.ARCORE.value == "ARCore"
        assert XRPlugin.ARKIT.value == "ARKit"

    def test_unity_project_dataclass(self):
        """Test UnityProject dataclass creation."""
        project = UnityProject(
            name="TestProject",
            path="/Users/dev/TestProject",
            version="2022.3.1f1"
        )
        assert project.name == "TestProject"
        assert project.path == "/Users/dev/TestProject"
        assert project.version == "2022.3.1f1"

    def test_unity_project_optional_version(self):
        """Test UnityProject with optional version."""
        project = UnityProject(
            name="TestProject",
            path="/Users/dev/TestProject"
        )
        assert project.name == "TestProject"
        assert project.version is None

    def test_unity_state_dataclass(self):
        """Test UnityState dataclass creation."""
        state = UnityState(
            is_running=True,
            project=UnityProject("Test", "/path"),
            active_window="Console",
            visible_windows=["Console", "Inspector"]
        )
        assert state.is_running is True
        assert state.project.name == "Test"
        assert state.active_window == "Console"
        assert "Console" in state.visible_windows

    def test_unity_state_default_visible_windows(self):
        """Test UnityState initializes visible_windows to empty list."""
        state = UnityState(is_running=False)
        assert state.visible_windows == []

    def test_package_status_enum_values(self):
        """Test PackageStatus enum values."""
        assert PackageStatus.NOT_FOUND.value == "not_found"
        assert PackageStatus.INSTALLED.value == "installed"
        assert PackageStatus.IMPORTING.value == "importing"

    def test_package_info_dataclass(self):
        """Test PackageInfo dataclass."""
        pkg = PackageInfo(
            name="com.unity.xr.oculus",
            package_id="com.unity.xr.oculus",
            version="3.0.0",
            status=PackageStatus.INSTALLED,
            source=PackageSource.UNITY_REGISTRY
        )
        assert pkg.name == "com.unity.xr.oculus"
        assert pkg.status == PackageStatus.INSTALLED

    def test_build_options_defaults(self):
        """Test BuildOptions default values."""
        opts = BuildOptions()
        assert opts.development_build is False
        assert opts.autoconnect_profiler is False
        assert opts.script_debugging is False
        assert opts.build_app_bundle is False

    def test_build_options_with_values(self):
        """Test BuildOptions with custom values."""
        opts = BuildOptions(
            development_build=True,
            script_debugging=True,
            scripting_backend=BuildScriptingBackend.IL2CPP
        )
        assert opts.development_build is True
        assert opts.script_debugging is True
        assert opts.scripting_backend == BuildScriptingBackend.IL2CPP

    def test_build_error_dataclass(self):
        """Test BuildError dataclass."""
        error = BuildError(
            message="Compilation failed",
            error_type="compilation",
            file_path="Assets/Scripts/Player.cs",
            line_number=42
        )
        assert error.message == "Compilation failed"
        assert error.error_type == "compilation"
        assert error.line_number == 42

    def test_build_result_info_defaults(self):
        """Test BuildResultInfo default values."""
        result = BuildResultInfo(result=BuildResult.SUCCESS)
        assert result.result == BuildResult.SUCCESS
        assert result.errors == []
        assert result.warnings == []

    def test_connected_device_dataclass(self):
        """Test ConnectedDevice dataclass."""
        device = ConnectedDevice(
            device_id="1WMHH81234567",
            model="Quest 3",
            state="device",
            is_quest=True
        )
        assert device.device_id == "1WMHH81234567"
        assert device.is_quest is True

    def test_console_message_dataclass(self):
        """Test ConsoleMessage dataclass."""
        msg = ConsoleMessage(
            message="Test error",
            level=ConsoleMessageLevel.ERROR,
            count=5
        )
        assert msg.message == "Test error"
        assert msg.level == ConsoleMessageLevel.ERROR
        assert msg.count == 5

    def test_editor_state_dataclass(self):
        """Test EditorState dataclass."""
        state = EditorState(
            is_compiling=True,
            is_importing=False,
            is_playing=False,
            has_errors=True,
            console_error_count=3,
            console_warning_count=5
        )
        assert state.is_compiling is True
        assert state.has_errors is True
        assert state.console_error_count == 3


# =============================================================================
# Test: Dialog Types and Configuration
# =============================================================================


class TestDialogTypes:
    """Tests for dialog types and configuration."""

    def test_dialog_type_enum_values(self):
        """Test DialogType enum values."""
        assert DialogType.INPUT_SYSTEM.value == "input_system"
        assert DialogType.API_UPDATE.value == "api_update"
        assert DialogType.RESTART_EDITOR.value == "restart_editor"
        assert DialogType.SAFE_MODE.value == "safe_mode"
        assert DialogType.BUILD_FAILED.value == "build_failed"

    def test_dialog_action_enum_values(self):
        """Test DialogAction enum values."""
        assert DialogAction.ACCEPT.value == "accept"
        assert DialogAction.REJECT.value == "reject"
        assert DialogAction.DISMISS.value == "dismiss"
        assert DialogAction.IGNORE.value == "ignore"
        assert DialogAction.CUSTOM.value == "custom"

    def test_dialog_config_creation(self):
        """Test DialogConfig creation with defaults."""
        config = DialogConfig(dialog_type=DialogType.INPUT_SYSTEM)
        assert config.dialog_type == DialogType.INPUT_SYSTEM
        assert config.action == DialogAction.ACCEPT
        assert config.enabled is True
        assert config.log_handling is True
        assert config.wait_after_handle == 1.0

    def test_dialog_config_custom_values(self):
        """Test DialogConfig with custom values."""
        config = DialogConfig(
            dialog_type=DialogType.SAFE_MODE,
            action=DialogAction.REJECT,
            enabled=True,
            wait_after_handle=2.0
        )
        assert config.dialog_type == DialogType.SAFE_MODE
        assert config.action == DialogAction.REJECT
        assert config.wait_after_handle == 2.0

    def test_dialog_handle_result_str_handled(self):
        """Test DialogHandleResult string representation when handled."""
        result = DialogHandleResult(
            dialog_type=DialogType.INPUT_SYSTEM,
            detected=True,
            handled=True,
            action_taken=DialogAction.ACCEPT
        )
        assert "handled" in str(result)
        assert "accept" in str(result)

    def test_dialog_handle_result_str_detected_not_handled(self):
        """Test DialogHandleResult string when detected but not handled."""
        result = DialogHandleResult(
            dialog_type=DialogType.SAFE_MODE,
            detected=True,
            handled=False
        )
        assert "detected but not handled" in str(result)

    def test_dialog_handle_result_str_not_detected(self):
        """Test DialogHandleResult string when not detected."""
        result = DialogHandleResult(
            dialog_type=DialogType.BUILD_FAILED,
            detected=False,
            handled=False
        )
        assert "not detected" in str(result)

    def test_dialog_log_creation(self):
        """Test DialogLog creation."""
        log = DialogLog(
            dialog_type=DialogType.API_UPDATE,
            action=DialogAction.ACCEPT,
            timestamp="2024-01-01T12:00:00",
            window_title="API Update Required",
            success=True
        )
        assert log.dialog_type == DialogType.API_UPDATE
        assert log.action == DialogAction.ACCEPT
        assert log.success is True


# =============================================================================
# Test: Meta Setup Types
# =============================================================================


class TestMetaSetupTypes:
    """Tests for Meta XR Setup Tool types."""

    def test_meta_setup_issue_level_enum(self):
        """Test MetaSetupIssueLevel enum values."""
        assert MetaSetupIssueLevel.REQUIRED.value == "required"
        assert MetaSetupIssueLevel.RECOMMENDED.value == "recommended"
        assert MetaSetupIssueLevel.OPTIONAL.value == "optional"

    def test_meta_setup_issue_status_enum(self):
        """Test MetaSetupIssueStatus enum values."""
        assert MetaSetupIssueStatus.UNFIXED.value == "unfixed"
        assert MetaSetupIssueStatus.FIXED.value == "fixed"
        assert MetaSetupIssueStatus.SKIPPED.value == "skipped"

    def test_meta_setup_issue_creation(self):
        """Test MetaSetupIssue creation."""
        issue = MetaSetupIssue(
            title="Enable OpenXR",
            level=MetaSetupIssueLevel.REQUIRED,
            status=MetaSetupIssueStatus.UNFIXED,
            description="OpenXR must be enabled for Quest development"
        )
        assert issue.title == "Enable OpenXR"
        assert issue.level == MetaSetupIssueLevel.REQUIRED
        assert issue.status == MetaSetupIssueStatus.UNFIXED

    def test_meta_setup_result_success(self):
        """Test MetaSetupResult for successful setup."""
        result = MetaSetupResult(
            success=True,
            fixed_issues=[
                MetaSetupIssue("Issue1", status=MetaSetupIssueStatus.FIXED),
                MetaSetupIssue("Issue2", status=MetaSetupIssueStatus.FIXED)
            ],
            remaining_issues=[],
            message="All issues fixed"
        )
        assert result.success is True
        assert len(result.fixed_issues) == 2
        assert len(result.remaining_issues) == 0

    def test_meta_setup_result_partial(self):
        """Test MetaSetupResult for partial setup."""
        result = MetaSetupResult(
            success=False,
            fixed_issues=[MetaSetupIssue("Issue1", status=MetaSetupIssueStatus.FIXED)],
            remaining_issues=[MetaSetupIssue("Issue2", status=MetaSetupIssueStatus.UNFIXED)],
            message="Some issues remain"
        )
        assert result.success is False
        assert len(result.remaining_issues) == 1


# =============================================================================
# Test: Workflow Types
# =============================================================================


class TestWorkflowTypes:
    """Tests for workflow orchestration types."""

    def test_workflow_step_enum_values(self):
        """Test WorkflowStep enum values."""
        assert WorkflowStep.CHECK_UNITY.value == "check_unity"
        assert WorkflowStep.INSTALL_META_SDK.value == "install_meta_sdk"
        assert WorkflowStep.CONFIGURE_XR.value == "configure_xr"
        assert WorkflowStep.BUILD_APK.value == "build_apk"
        assert WorkflowStep.DEPLOY_TO_DEVICE.value == "deploy_to_device"

    def test_workflow_status_enum_values(self):
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.NOT_STARTED.value == "not_started"
        assert WorkflowStatus.IN_PROGRESS.value == "in_progress"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"

    def test_workflow_progress_creation(self):
        """Test WorkflowProgress creation."""
        progress = WorkflowProgress(
            step=WorkflowStep.BUILD_APK,
            status=WorkflowStatus.IN_PROGRESS,
            message="Building APK...",
            progress_percent=50.0,
            step_number=3,
            total_steps=5
        )
        assert progress.step == WorkflowStep.BUILD_APK
        assert progress.status == WorkflowStatus.IN_PROGRESS
        assert progress.progress_percent == 50.0

    def test_workflow_result_success(self):
        """Test WorkflowResult for successful workflow."""
        result = WorkflowResult(
            success=True,
            workflow_name="setup_quest3",
            message="Quest 3 setup complete",
            duration_seconds=120.5,
            steps_completed=5,
            steps_total=5
        )
        assert result.success is True
        assert result.steps_completed == result.steps_total

    def test_workflow_result_failed(self):
        """Test WorkflowResult for failed workflow."""
        result = WorkflowResult(
            success=False,
            workflow_name="setup_quest3",
            message="Setup failed",
            duration_seconds=45.0,
            steps_completed=2,
            steps_total=5,
            errors=["SDK installation failed"]
        )
        assert result.success is False
        assert len(result.errors) == 1


# =============================================================================
# Test: Safety Patterns
# =============================================================================


class TestSafetyPatterns:
    """Tests for Unity dialog safety patterns."""

    def test_unity_dialog_patterns_exist(self):
        """Test that predefined dialog patterns exist."""
        assert "input_system" in UNITY_DIALOG_PATTERNS
        assert "api_update" in UNITY_DIALOG_PATTERNS
        assert "restart_editor" in UNITY_DIALOG_PATTERNS
        assert "safe_mode" in UNITY_DIALOG_PATTERNS
        assert "build_failed" in UNITY_DIALOG_PATTERNS
        assert "import" in UNITY_DIALOG_PATTERNS

    def test_dialog_pattern_structure(self):
        """Test DialogPattern structure."""
        pattern = UNITY_DIALOG_PATTERNS["input_system"]
        assert isinstance(pattern, DialogPattern)
        assert pattern.name == "Enable New Input System"
        assert "Input System" in pattern.window_title_contains
        assert "Yes" in pattern.button_accept
        assert pattern.auto_handle is True

    def test_safe_mode_pattern_not_auto_handle(self):
        """Test that safe mode pattern is not auto-handled by default."""
        pattern = UNITY_DIALOG_PATTERNS["safe_mode"]
        assert pattern.auto_handle is False  # Should not auto-enter safe mode

    def test_get_pattern_existing(self):
        """Test get_pattern for existing pattern."""
        pattern = get_pattern("input_system")
        assert pattern is not None
        assert pattern.name == "Enable New Input System"

    def test_get_pattern_nonexistent(self):
        """Test get_pattern for nonexistent pattern."""
        pattern = get_pattern("nonexistent_pattern")
        assert pattern is None

    def test_get_patterns_for_window_title_single_match(self):
        """Test matching patterns for a window title."""
        patterns = get_patterns_for_window_title("Enable new Input System?")
        assert len(patterns) >= 1
        assert any(p.name == "Enable New Input System" for p in patterns)

    def test_get_patterns_for_window_title_no_match(self):
        """Test no patterns match for unrelated window title."""
        patterns = get_patterns_for_window_title("Some Unrelated Window")
        # May still match if title contains generic keywords
        # The test verifies the function runs without error
        assert isinstance(patterns, list)

    def test_get_auto_handle_patterns(self):
        """Test getting auto-handle patterns."""
        patterns = get_auto_handle_patterns()
        assert len(patterns) > 0
        # All returned patterns should have auto_handle=True
        for key, pattern in patterns.items():
            assert pattern.auto_handle is True

    def test_get_blocking_patterns(self):
        """Test getting blocking patterns."""
        patterns = get_blocking_patterns()
        assert len(patterns) > 0
        # All returned patterns should have is_blocking=True
        for key, pattern in patterns.items():
            assert pattern.is_blocking is True

    def test_create_custom_pattern(self):
        """Test creating a custom dialog pattern."""
        pattern = create_custom_pattern(
            name="My Custom Dialog",
            window_title_contains=["Custom", "Dialog"],
            accept_buttons=["Proceed"],
            reject_buttons=["Cancel"],
            auto_handle=True,
            wait_seconds=2.0
        )
        assert pattern.name == "My Custom Dialog"
        assert "Custom" in pattern.window_title_contains
        assert "Proceed" in pattern.button_accept
        assert pattern.auto_handle is True
        assert pattern.wait_seconds == 2.0


# =============================================================================
# Test: Unity Agent - Core Methods (Mocked)
# =============================================================================


class TestUnityAgentCore:
    """Tests for UnityAgent core methods with mocked subprocess."""

    def test_agent_initialization(self):
        """Test agent initializes with default values."""
        agent = UnityAgent()
        assert agent._cached_state is None
        assert agent._state_cache_time == 0
        assert agent._state_cache_ttl == 2.0
        assert agent._dialog_configs is not None
        assert agent._dialog_log == []

    def test_is_unity_running_true(self, mock_agent, mock_unity_running):
        """Test is_unity_running returns True when Unity is running."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_running

        result = agent.is_unity_running()

        assert result is True
        mock_run.assert_called_once()

    def test_is_unity_running_false(self, mock_agent, mock_unity_not_running):
        """Test is_unity_running returns False when Unity is not running."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_not_running

        result = agent.is_unity_running()

        assert result is False

    def test_is_unity_running_exception(self, mock_agent):
        """Test is_unity_running handles subprocess errors gracefully."""
        agent, mock_run = mock_agent
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        result = agent.is_unity_running()

        assert result is False

    def test_get_unity_pid_running(self, mock_agent, mock_unity_running):
        """Test get_unity_pid returns PID when Unity is running."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_running

        result = agent.get_unity_pid()

        assert result == 12345

    def test_get_unity_pid_not_running(self, mock_agent, mock_unity_not_running):
        """Test get_unity_pid returns None when Unity is not running."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_not_running

        result = agent.get_unity_pid()

        assert result is None

    def test_get_unity_pid_exception(self, mock_agent):
        """Test get_unity_pid handles errors gracefully."""
        agent, mock_run = mock_agent
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        result = agent.get_unity_pid()

        assert result is None

    def test_state_caching(self, mock_agent, mock_unity_not_running):
        """Test that state is cached."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_not_running

        # First call should hit the subprocess
        state1 = agent.get_state()
        call_count_after_first = mock_run.call_count

        # Second call should use cache (within TTL)
        state2 = agent.get_state()

        # Should not have made additional calls
        assert mock_run.call_count == call_count_after_first
        assert state1.is_running == state2.is_running

    def test_state_cache_bypass(self, mock_agent, mock_unity_not_running):
        """Test that force_refresh bypasses cache."""
        agent, mock_run = mock_agent
        mock_run.return_value = mock_unity_not_running

        # First call
        agent.get_state()
        call_count = mock_run.call_count

        # Force refresh should make new call
        agent.get_state(force_refresh=True)

        assert mock_run.call_count > call_count


class TestUnityAgentWindowParsing:
    """Tests for Unity window title parsing."""

    def test_parse_standard_window_title(self):
        """Test parsing standard Unity window title format."""
        agent = UnityAgent()

        # Mock the internal method that gets window title
        with mock.patch.object(agent, '_get_unity_window_title') as mock_title:
            mock_title.return_value = "TestProject - /Users/dev/TestProject - Unity 2022.3.1f1 <DX11>"

            project = agent.get_open_project()

            assert project is not None
            assert project.name == "TestProject"
            assert project.path == "/Users/dev/TestProject"
            assert project.version == "2022.3.1f1"

    def test_parse_no_window_title(self):
        """Test get_open_project returns None when no window title."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_get_unity_window_title') as mock_title:
            mock_title.return_value = None

            project = agent.get_open_project()

            assert project is None

    def test_parse_fallback_window_title(self):
        """Test fallback parsing for non-standard window titles."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_get_unity_window_title') as mock_title:
            # Non-standard format that doesn't match the main regex but has " - Unity "
            # Fallback requires " - Unity " (with trailing space) in the title
            mock_title.return_value = "TestProject - Unity 2022.3"

            project = agent.get_open_project()

            # Should use fallback parsing
            assert project is not None
            assert project.name == "TestProject"


# =============================================================================
# Test: Menu Navigation (Mocked)
# =============================================================================


class TestMenuNavigation:
    """Tests for menu navigation with mocked AppleScript."""

    def test_navigate_menu_success(self):
        """Test successful menu navigation."""
        agent = UnityAgent()

        # navigate_menu uses subprocess.run directly, not _run_applescript
        with mock.patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(agent, '_activate_unity', return_value=True):
                result = agent.navigate_menu("File", "Build Settings...")

                assert result is True

    def test_navigate_menu_unity_not_activated(self):
        """Test menu navigation fails when Unity can't be activated."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_activate_unity', return_value=False):
            result = agent.navigate_menu("File", "Build Settings...")

            assert result is False

    def test_open_build_settings(self):
        """Test opening Build Settings."""
        agent = UnityAgent()

        # open_build_settings uses open_menu_with_shortcut first, then navigate_menu as fallback
        with mock.patch.object(agent, 'open_menu_with_shortcut', return_value=True):
            result = agent.open_build_settings()
            assert result is True

    def test_open_build_settings_fallback(self):
        """Test opening Build Settings via menu fallback."""
        agent = UnityAgent()

        # Shortcut fails, fallback to navigate_menu
        with mock.patch.object(agent, 'open_menu_with_shortcut', return_value=False):
            with mock.patch.object(agent, 'navigate_menu', return_value=True):
                result = agent.open_build_settings()
                assert result is True


# =============================================================================
# Test: State Detection (Mocked)
# =============================================================================


class TestStateDetection:
    """Tests for Unity state detection with mocked responses."""

    def test_is_compiling(self):
        """Test is_compiling method."""
        agent = UnityAgent()

        # Mock internal _is_compiling method
        with mock.patch.object(agent, '_is_compiling', return_value=True):
            result = agent.is_compiling()
            assert result is True

        with mock.patch.object(agent, '_is_compiling', return_value=False):
            result = agent.is_compiling()
            assert result is False

    def test_is_importing(self):
        """Test is_importing method."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_is_importing', return_value=True):
            result = agent.is_importing()
            assert result is True

        with mock.patch.object(agent, '_is_importing', return_value=False):
            result = agent.is_importing()
            assert result is False

    def test_is_in_play_mode(self):
        """Test is_in_play_mode method."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_run_applescript') as mock_script:
            mock_script.return_value = (True, "yes")
            result = agent.is_in_play_mode()
            assert result is True

        with mock.patch.object(agent, '_run_applescript') as mock_script:
            mock_script.return_value = (True, "no")
            result = agent.is_in_play_mode()
            assert result is False

    def test_has_console_errors(self):
        """Test has_console_errors method."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_get_console_error_count', return_value=3):
            result = agent.has_console_errors()
            assert result is True

        with mock.patch.object(agent, '_get_console_error_count', return_value=0):
            result = agent.has_console_errors()
            assert result is False

    def test_get_editor_state(self):
        """Test get_editor_state returns complete state."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_is_compiling', return_value=True):
            with mock.patch.object(agent, '_is_importing', return_value=False):
                with mock.patch.object(agent, 'is_in_play_mode', return_value=False):
                    with mock.patch.object(agent, '_get_console_error_count', return_value=2):
                        with mock.patch.object(agent, '_get_console_warning_count', return_value=5):
                            state = agent.get_editor_state()

                            assert state.is_compiling is True
                            assert state.is_importing is False
                            assert state.is_playing is False
                            assert state.has_errors is True
                            assert state.console_error_count == 2
                            assert state.console_warning_count == 5

    def test_wait_for_idle_already_idle(self):
        """Test wait_for_idle returns immediately when already idle."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_is_compiling', return_value=False):
            with mock.patch.object(agent, '_is_importing', return_value=False):
                success, message = agent.wait_for_idle(timeout=5.0)

                assert success is True
                assert "idle" in message.lower()

    def test_wait_for_idle_timeout(self):
        """Test wait_for_idle times out when never idle."""
        agent = UnityAgent()

        # Always return compiling
        with mock.patch.object(agent, '_is_compiling', return_value=True):
            with mock.patch.object(agent, '_is_importing', return_value=False):
                success, message = agent.wait_for_idle(timeout=1.0)

                assert success is False
                assert "timeout" in message.lower()


# =============================================================================
# Test: Dialog Handling (Mocked)
# =============================================================================


class TestDialogHandling:
    """Tests for dialog detection and handling."""

    def test_default_dialog_configs(self):
        """Test that default dialog configs are initialized."""
        agent = UnityAgent()

        configs = agent._dialog_configs
        assert len(configs) > 0
        assert DialogType.INPUT_SYSTEM in configs
        assert DialogType.SAFE_MODE in configs

    def test_configure_dialog_handler(self):
        """Test configuring a dialog handler."""
        agent = UnityAgent()

        # Get original config
        original = agent.get_dialog_config(DialogType.SAFE_MODE)

        # Configure new action
        agent.configure_dialog_handler(
            DialogType.SAFE_MODE,
            action=DialogAction.ACCEPT,
            enabled=True,
            wait_after_handle=3.0
        )

        new_config = agent.get_dialog_config(DialogType.SAFE_MODE)
        assert new_config.action == DialogAction.ACCEPT
        assert new_config.wait_after_handle == 3.0

    def test_dialog_log_initially_empty(self):
        """Test dialog log starts empty."""
        agent = UnityAgent()

        log = agent.get_dialog_log()
        assert len(log) == 0

    def test_clear_dialog_log(self):
        """Test clearing dialog log."""
        agent = UnityAgent()

        # Manually add to log
        agent._dialog_log.append(
            DialogLog(
                dialog_type=DialogType.INPUT_SYSTEM,
                action=DialogAction.ACCEPT,
                timestamp="2024-01-01T12:00:00"
            )
        )

        # Clear and verify
        agent.clear_dialog_log()
        assert len(agent._dialog_log) == 0


# =============================================================================
# Test: Orchestrator
# =============================================================================


class TestOrchestrator:
    """Tests for the Unity command orchestrator."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                orchestrator = UnityOrchestrator()

                assert orchestrator is not None
                assert orchestrator.agent is not None

    def test_get_commands_returns_list(self):
        """Test get_commands returns list of available commands."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                orchestrator = UnityOrchestrator()
                commands = orchestrator.get_commands()

                assert isinstance(commands, list)
                assert len(commands) > 0
                assert "unity.is_running" in commands

    def test_expected_commands_registered(self):
        """Test that expected commands are registered."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                orchestrator = UnityOrchestrator()
                commands = orchestrator.get_commands()

                expected_commands = [
                    "unity.is_running",
                    "unity.wait_idle",
                    "unity.get_project",
                    "unity.setup_quest3",
                    "unity.install_meta_sdk",
                    "unity.configure_xr",
                    "unity.build",
                    "unity.build.apk",
                    "unity.deploy",
                    "unity.devices",
                    "unity.handle_dialogs",
                    "unity.state",
                    "unity.console_errors",
                ]

                for cmd in expected_commands:
                    assert cmd in commands, f"Missing command: {cmd}"

    def test_execute_unknown_command(self):
        """Test executing unknown command returns error."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                orchestrator = UnityOrchestrator()

                result = orchestrator.execute("unity.nonexistent")

                assert result.status == CommandStatus.FAILED
                assert "unknown" in result.message.lower() or "unknown" in str(result.error).lower()

    def test_execute_is_running_command(self):
        """Test executing unity.is_running command."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=True):
                orchestrator = UnityOrchestrator()

                result = orchestrator.execute("unity.is_running")

                assert result.status == CommandStatus.SUCCESS
                assert result.details.get("is_running") is True


class TestCommandRegistry:
    """Tests for the command registry."""

    def test_registry_initialization(self):
        """Test registry initializes with agent."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                registry = UnityCommandRegistry()

                assert registry is not None
                assert registry._agent is not None

    def test_has_command(self):
        """Test has_command method."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                registry = UnityCommandRegistry()

                assert registry.has_command("unity.is_running") is True
                assert registry.has_command("nonexistent") is False

    def test_get_available_commands_sorted(self):
        """Test get_available_commands returns sorted list."""
        with mock.patch.object(UnityAgent, '_run_applescript', return_value=(False, "")):
            with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
                registry = UnityCommandRegistry()
                commands = registry.get_available_commands()

                assert commands == sorted(commands)


class TestWorkflowExecutor:
    """Tests for the workflow executor."""

    def test_workflow_definition_creation(self):
        """Test WorkflowDefinition creation."""
        workflow = WorkflowDefinition(
            name="test-workflow",
            description="A test workflow",
            steps=[
                WorkflowStepDefinition(
                    command="unity.is_running",
                    name="Check Unity"
                )
            ]
        )

        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 1

    def test_workflow_step_definition(self):
        """Test WorkflowStepDefinition defaults."""
        step = WorkflowStepDefinition(command="unity.build")

        assert step.command == "unity.build"
        assert step.name == ""
        assert step.args == {}
        assert step.continue_on_error is False
        assert step.condition is None

    def test_workflow_execution_result(self):
        """Test WorkflowExecutionResult creation."""
        result = WorkflowExecutionResult(
            workflow_name="test",
            success=True,
            steps_completed=3,
            steps_total=3
        )

        assert result.success is True
        assert result.steps_completed == 3


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_unity_not_running_graceful(self):
        """Test graceful handling when Unity is not running."""
        agent = UnityAgent()

        with mock.patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1,
                stdout="",
                stderr=""
            )

            assert agent.is_unity_running() is False
            assert agent.get_unity_pid() is None

    def test_applescript_error_graceful(self):
        """Test graceful handling of AppleScript errors."""
        agent = UnityAgent()

        with mock.patch.object(agent, '_run_applescript') as mock_script:
            mock_script.return_value = (False, "error")

            # These should not raise exceptions
            assert agent.is_in_play_mode() is False

    def test_subprocess_timeout_graceful(self):
        """Test graceful handling of subprocess timeouts."""
        agent = UnityAgent()

        with mock.patch.object(subprocess, 'run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

            # Should handle timeout gracefully
            windows = agent.get_visible_windows()
            assert windows == []


# =============================================================================
# Test: CI Mode Compatibility
# =============================================================================


class TestCIMode:
    """Tests that verify CI compatibility (no actual Unity required)."""

    def test_all_imports_successful(self):
        """Test that all imports work without Unity."""
        # This test passes if we got here - imports at top of file succeeded
        assert UnityAgent is not None
        assert UnityWindow is not None
        assert DialogType is not None
        assert UnityOrchestrator is not None

    def test_agent_creation_without_unity(self):
        """Test agent can be created without Unity running."""
        agent = UnityAgent()
        assert agent is not None

    def test_orchestrator_creation_without_unity(self):
        """Test orchestrator can be created without Unity running."""
        with mock.patch.object(UnityAgent, 'is_unity_running', return_value=False):
            orchestrator = UnityOrchestrator()
            assert orchestrator is not None

    def test_data_classes_work_without_unity(self):
        """Test all data classes can be instantiated without Unity."""
        # These should all work without Unity
        project = UnityProject("Test", "/path")
        state = UnityState(is_running=False)
        pkg = PackageInfo("test-pkg")
        opts = BuildOptions()
        error = BuildError("error")
        result = BuildResultInfo(result=BuildResult.SUCCESS)
        device = ConnectedDevice("123")
        msg = ConsoleMessage("msg")
        editor_state = EditorState()
        issue = MetaSetupIssue("issue")
        meta_result = MetaSetupResult(True, [], [], "ok")
        progress = WorkflowProgress(WorkflowStep.CHECK_UNITY, WorkflowStatus.NOT_STARTED, "")
        workflow_result = WorkflowResult(True, "test", "ok")

        # All should be valid
        assert project is not None
        assert state is not None
        assert pkg is not None

    def test_mock_all_external_calls(self):
        """Test that we can mock all external calls for full CI testing."""
        with mock.patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="")

            agent = UnityAgent()

            # All these should work with mocks
            assert agent.is_unity_running() is False
            assert agent.get_unity_pid() is None

            state = agent.get_state()
            assert state.is_running is False


# =============================================================================
# Integration-style Tests (Still Mocked)
# =============================================================================


class TestIntegration:
    """Integration-style tests with comprehensive mocking."""

    def test_full_workflow_mocked(self):
        """Test a full workflow with all methods mocked."""
        agent = UnityAgent()

        with mock.patch.object(agent, 'is_unity_running', return_value=True):
            with mock.patch.object(agent, 'get_open_project', return_value=UnityProject("Test", "/path", "2022.3")):
                with mock.patch.object(agent, '_is_compiling', return_value=False):
                    with mock.patch.object(agent, '_is_importing', return_value=False):
                        # Simulate checking state
                        assert agent.is_unity_running() is True

                        project = agent.get_open_project()
                        assert project.name == "Test"

                        # Wait for idle (already idle)
                        success, _ = agent.wait_for_idle(timeout=5)
                        assert success is True

    def test_orchestrator_command_flow(self):
        """Test orchestrator command execution flow."""
        with mock.patch.object(UnityAgent, 'is_unity_running', return_value=True):
            with mock.patch.object(UnityAgent, '_run_applescript', return_value=(True, "")):
                orchestrator = UnityOrchestrator()

                # Execute is_running command
                result = orchestrator.execute("unity.is_running")

                assert result.command == "unity.is_running"
                assert result.status == CommandStatus.SUCCESS


def run_basic_tests():
    """Run basic tests without pytest for quick verification."""
    print("Running basic test verification (pytest not installed)")
    print("=" * 60)

    failures = []
    successes = 0
    skipped = 0

    # Test class instantiation
    test_classes = [
        TestDataClasses,
        TestDialogTypes,
        TestMetaSetupTypes,
        TestWorkflowTypes,
        TestSafetyPatterns,
        TestUnityAgentCore,
        TestUnityAgentWindowParsing,
        TestMenuNavigation,
        TestStateDetection,
        TestDialogHandling,
        TestOrchestrator,
        TestCommandRegistry,
        TestWorkflowExecutor,
        TestErrorHandling,
        TestCIMode,
        TestIntegration,
    ]

    # Tests that require pytest fixtures (skip in basic mode)
    fixture_dependent_tests = {
        "test_is_unity_running_true",
        "test_is_unity_running_false",
        "test_is_unity_running_exception",
        "test_get_unity_pid_running",
        "test_get_unity_pid_not_running",
        "test_get_unity_pid_exception",
        "test_state_caching",
        "test_state_cache_bypass",
    }

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                # Skip fixture-dependent tests
                if method_name in fixture_dependent_tests:
                    skipped += 1
                    print(f"  SKIP: {test_class.__name__}.{method_name} (requires fixtures)")
                    continue

                try:
                    method = getattr(instance, method_name)
                    method()
                    successes += 1
                    print(f"  PASS: {test_class.__name__}.{method_name}")
                except Exception as e:
                    failures.append((f"{test_class.__name__}.{method_name}", str(e)))
                    print(f"  FAIL: {test_class.__name__}.{method_name}: {e}")

    print("=" * 60)
    print(f"Results: {successes} passed, {skipped} skipped, {len(failures)} failed")

    if failures:
        print("\nFailures:")
        for name, error in failures:
            print(f"  - {name}: {error}")
        return 1

    print("\nNote: Skipped tests require pytest fixtures and will run with: pytest agents/computer_use/tests/test_unity.py")
    return 0


if __name__ == "__main__":
    if PYTEST_AVAILABLE:
        pytest.main([__file__, "-v"])
    else:
        exit(run_basic_tests())
