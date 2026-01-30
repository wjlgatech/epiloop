#!/usr/bin/env python3
"""
unity.py - Unity Editor Automation for macOS

This module provides automation capabilities for Unity Editor on macOS,
extending the computer_use agent patterns with Unity-specific commands.
Designed for Quest 3 XR development workflows.

Usage:
    from agents.computer_use.unity import UnityAgent

    agent = UnityAgent()
    if agent.is_unity_running():
        agent.navigate_menu("File", "Build Settings...")
"""

import json
import logging
import subprocess
import time
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple, Callable, Any

# Optional imports for vision-based clicking
try:
    from .click_helper import ClickHelper, ClickResult, ClickMethod
    CLICK_HELPER_AVAILABLE = True
except ImportError:
    CLICK_HELPER_AVAILABLE = False

    # Placeholder classes when click_helper is not available
    class ClickMethod(Enum):  # type: ignore[no-redef]
        """Placeholder ClickMethod when click_helper unavailable."""
        APPLESCRIPT = "applescript"
        VISION_QUARTZ = "vision_quartz"
        COORDINATES = "coordinates"
        FAILED = "failed"

    @dataclass
    class ClickResult:  # type: ignore[no-redef]
        """Placeholder ClickResult when click_helper unavailable."""
        success: bool
        method: 'ClickMethod'
        x: Optional[float] = None
        y: Optional[float] = None
        confidence: Optional[float] = None
        error_message: Optional[str] = None
        applescript_tried: bool = False
        vision_tried: bool = False
        before_screenshot: Optional[bytes] = None
        after_screenshot: Optional[bytes] = None

    ClickHelper = None  # type: ignore

# Optional imports for multi-monitor screenshot capture
try:
    from .screenshot import (
        MultiMonitorCapture,
        capture_screenshot,
        coordinate_to_display,
        display_to_global,
        ScreenshotResult,
    )
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False
    MultiMonitorCapture = None  # type: ignore
    capture_screenshot = None  # type: ignore
    coordinate_to_display = None  # type: ignore
    display_to_global = None  # type: ignore
    ScreenshotResult = None  # type: ignore

# Optional imports for Unity log monitoring
try:
    from .unity_monitor import (
        UnityLogMonitor,
        BuildEventType,
        BuildPhase,
        BuildMonitorResult,
        get_unity_log_path,
        monitor_unity_build,
    )
    LOG_MONITOR_AVAILABLE = True
except ImportError:
    LOG_MONITOR_AVAILABLE = False
    UnityLogMonitor = None  # type: ignore
    BuildEventType = None  # type: ignore
    BuildPhase = None  # type: ignore
    BuildMonitorResult = None  # type: ignore
    get_unity_log_path = None  # type: ignore
    monitor_unity_build = None  # type: ignore

# Optional imports for dialog registry
try:
    from .dialog_registry import (
        DialogRegistry,
        DialogHandler,
        DialogActionType,
        DialogMatchType,
        DialogMatchResult,
        DialogActionResult,
        load_dialog_registry,
        YAML_AVAILABLE,
    )
    DIALOG_REGISTRY_AVAILABLE = True
except ImportError:
    DIALOG_REGISTRY_AVAILABLE = False
    DialogRegistry = None  # type: ignore
    DialogHandler = None  # type: ignore
    DialogActionType = None  # type: ignore
    DialogMatchType = None  # type: ignore
    DialogMatchResult = None  # type: ignore
    DialogActionResult = None  # type: ignore
    load_dialog_registry = None  # type: ignore
    YAML_AVAILABLE = False

# Optional imports for workflow checkpointing
try:
    from .checkpoint import (
        WorkflowCheckpoint,
        CheckpointData,
        list_checkpoints,
        load_latest_checkpoint,
        cleanup_checkpoints,
    )
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False
    WorkflowCheckpoint = None  # type: ignore
    CheckpointData = None  # type: ignore
    list_checkpoints = None  # type: ignore
    load_latest_checkpoint = None  # type: ignore
    cleanup_checkpoints = None  # type: ignore

# Optional imports for unified click handler (GUI-004)
try:
    from .click_handler import (
        ClickHandler as UnifiedClickHandler,
        ClickHandlerResult,
        ClickMethod as UnifiedClickMethod,
        FallbackReason,
        ElementBounds,
    )
    UNIFIED_CLICK_HANDLER_AVAILABLE = True
except ImportError:
    UNIFIED_CLICK_HANDLER_AVAILABLE = False
    UnifiedClickHandler = None  # type: ignore
    ClickHandlerResult = None  # type: ignore
    UnifiedClickMethod = None  # type: ignore
    FallbackReason = None  # type: ignore
    ElementBounds = None  # type: ignore

# Optional imports for Unity panel detection (GUI-005)
try:
    from .unity_panels import (
        UnityPanelDetector,
        PanelType,
        PanelLayout,
        PanelBounds,
        PanelDetectionResult,
        ButtonInPanelResult,
        ClickInPanelResult,
    )
    UNITY_PANELS_AVAILABLE = True
except ImportError:
    UNITY_PANELS_AVAILABLE = False
    UnityPanelDetector = None  # type: ignore
    PanelType = None  # type: ignore
    PanelLayout = None  # type: ignore
    PanelBounds = None  # type: ignore
    PanelDetectionResult = None  # type: ignore
    ButtonInPanelResult = None  # type: ignore
    ClickInPanelResult = None  # type: ignore

# Optional imports for vision element state detection (GUI-006)
try:
    from .vision_detector import (
        VisionDetector,
        ElementState,
        ButtonState,
        CheckboxState,
        ProgressState,
        DetectionResult,
        BoundingBox,
    )
    VISION_DETECTOR_AVAILABLE = True
except ImportError:
    VISION_DETECTOR_AVAILABLE = False
    VisionDetector = None  # type: ignore
    ElementState = None  # type: ignore
    ButtonState = None  # type: ignore
    CheckboxState = None  # type: ignore
    ProgressState = None  # type: ignore
    DetectionResult = None  # type: ignore
    BoundingBox = None  # type: ignore

# Optional imports for wait utilities (GUI-008)
try:
    from .wait_utils import (
        WaitHelper,
        WaitResult,
        WaitOutcome,
        WaitProgress,
    )
    WAIT_UTILS_AVAILABLE = True
except ImportError:
    WAIT_UTILS_AVAILABLE = False
    WaitHelper = None  # type: ignore
    WaitResult = None  # type: ignore
    WaitOutcome = None  # type: ignore
    WaitProgress = None  # type: ignore

# Set up logging
logger = logging.getLogger(__name__)


class UnityWindow(Enum):
    """Unity Editor windows that can be detected and interacted with."""
    PROJECT = "Project"
    HIERARCHY = "Hierarchy"
    INSPECTOR = "Inspector"
    CONSOLE = "Console"
    SCENE = "Scene"
    GAME = "Game"
    ANIMATOR = "Animator"
    PACKAGE_MANAGER = "Package Manager"
    PROJECT_SETTINGS = "Project Settings"
    BUILD_SETTINGS = "Build Settings"
    XR_PLUGIN_MANAGEMENT = "XR Plug-in Management"
    META_PROJECT_SETUP = "Project Setup Tool"


class ProjectSettingsCategory(Enum):
    """Project Settings categories that can be navigated to."""
    PLAYER = "Player"
    INPUT_MANAGER = "Input Manager"
    TAGS_AND_LAYERS = "Tags and Layers"
    PHYSICS = "Physics"
    PHYSICS_2D = "Physics 2D"
    TIME = "Time"
    QUALITY = "Quality"
    GRAPHICS = "Graphics"
    AUDIO = "Audio"
    EDITOR = "Editor"
    SCRIPTING = "Scripting"
    SCRIPT_EXECUTION_ORDER = "Script Execution Order"
    XR_PLUGIN_MANAGEMENT = "XR Plug-in Management"
    XR_INTERACTION_TOOLKIT = "XR Interaction Toolkit"


class Platform(Enum):
    """Build platforms supported by Unity."""
    STANDALONE = "Standalone"
    ANDROID = "Android"
    IOS = "iOS"
    WEBGL = "WebGL"
    WINDOWS_SERVER = "Windows Server"
    LINUX_SERVER = "Linux Server"
    MACOS_SERVER = "macOS Server"


class XRPlugin(Enum):
    """XR plugins that can be enabled."""
    OCULUS = "Oculus"
    OPEN_XR = "OpenXR"
    ARCORE = "ARCore"
    ARKIT = "ARKit"
    MOCK_HMD = "Mock HMD"
    UNITY_MOCK_HMD = "Unity Mock HMD"


class PackageStatus(Enum):
    """Status of a Unity package."""
    NOT_FOUND = "not_found"
    AVAILABLE = "available"
    INSTALLED = "installed"
    IMPORTING = "importing"
    UPDATE_AVAILABLE = "update_available"


class PackageSource(Enum):
    """Source of a Unity package."""
    UNITY_REGISTRY = "unity_registry"
    ASSET_STORE = "my_assets"
    IN_PROJECT = "in_project"


@dataclass
class PackageInfo:
    """Information about a Unity package."""
    name: str
    package_id: Optional[str] = None
    version: Optional[str] = None
    status: PackageStatus = PackageStatus.NOT_FOUND
    source: PackageSource = PackageSource.UNITY_REGISTRY


class UnityMenu(Enum):
    """Unity Editor main menu items."""
    FILE = "File"
    EDIT = "Edit"
    ASSETS = "Assets"
    GAMEOBJECT = "GameObject"
    COMPONENT = "Component"
    JOBS = "Jobs"
    WINDOW = "Window"
    HELP = "Help"
    # Meta XR SDK adds this menu when installed
    META = "Meta"


@dataclass
class UnityProject:
    """Information about the currently open Unity project."""
    name: str
    path: str
    version: Optional[str] = None


@dataclass
class UnityState:
    """Current state of the Unity Editor."""
    is_running: bool
    project: Optional[UnityProject] = None
    active_window: Optional[str] = None
    visible_windows: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.visible_windows is None:
            self.visible_windows = []


class BuildTargetPlatform(Enum):
    """Build target platforms supported by Unity."""
    STANDALONE_WINDOWS = "Win"
    STANDALONE_WINDOWS64 = "Win64"
    STANDALONE_MACOS = "OSXUniversal"
    STANDALONE_LINUX64 = "Linux64"
    ANDROID = "Android"
    IOS = "iOS"
    WEBGL = "WebGL"
    TVOS = "tvOS"
    PS4 = "PS4"
    PS5 = "PS5"
    XBOX_ONE = "XboxOne"
    SWITCH = "Switch"


class BuildScriptingBackend(Enum):
    """Scripting backend options."""
    MONO = "Mono2x"
    IL2CPP = "IL2CPP"


class BuildResult(Enum):
    """Result of a build operation."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class BuildOptions:
    """Options for Unity build configuration."""
    development_build: bool = False
    autoconnect_profiler: bool = False
    deep_profiling: bool = False
    script_debugging: bool = False
    compression_method: Optional[str] = None  # "LZ4", "LZ4HC", "None"
    build_app_bundle: bool = False  # For Android AAB vs APK
    export_project: bool = False  # Export Android Studio project
    scripting_backend: Optional[BuildScriptingBackend] = None


@dataclass
class BuildError:
    """Information about a build error."""
    message: str
    error_type: str = "unknown"  # "compilation", "asset", "manifest", "signing", etc.
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    details: Optional[str] = None


@dataclass
class BuildResultInfo:
    """Result of a build operation with detailed information."""
    result: BuildResult
    output_path: Optional[str] = None
    build_time_seconds: float = 0.0
    errors: Optional[List[BuildError]] = None
    warnings: Optional[List[str]] = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class ConnectedDevice:
    """Information about a connected device (via ADB)."""
    device_id: str
    model: str = "Unknown"
    state: str = "device"  # "device", "offline", "unauthorized"
    is_quest: bool = False


class MetaSetupIssueLevel(Enum):
    """Severity level of a Meta XR Setup Tool issue."""
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class MetaSetupIssueStatus(Enum):
    """Status of a Meta XR Setup Tool issue."""
    UNFIXED = "unfixed"
    FIXED = "fixed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class MetaSetupIssue:
    """Represents a single issue in the Meta XR Project Setup Tool."""
    title: str
    level: MetaSetupIssueLevel = MetaSetupIssueLevel.RECOMMENDED
    status: MetaSetupIssueStatus = MetaSetupIssueStatus.UNFIXED
    description: Optional[str] = None


@dataclass
class MetaSetupResult:
    """Result of running Meta XR Project Setup Tool operations."""
    success: bool
    fixed_issues: List[MetaSetupIssue]
    remaining_issues: List[MetaSetupIssue]
    message: str
    meta_sdk_installed: bool = True


class ConsoleMessageLevel(Enum):
    """Unity Console message severity levels."""
    LOG = "log"
    WARNING = "warning"
    ERROR = "error"
    EXCEPTION = "exception"
    ASSERT = "assert"


@dataclass
class ConsoleMessage:
    """Represents a message from the Unity Console window."""
    message: str
    level: ConsoleMessageLevel = ConsoleMessageLevel.LOG
    timestamp: Optional[str] = None
    stack_trace: Optional[str] = None
    count: int = 1  # For collapsed messages


@dataclass
class EditorState:
    """Current state of the Unity Editor for idle detection."""
    is_compiling: bool = False
    is_importing: bool = False
    is_playing: bool = False
    has_errors: bool = False
    console_error_count: int = 0
    console_warning_count: int = 0


# =============================================================================
# Vision-Based Automation Result Types (GUI-009)
# =============================================================================


class VisionWorkflowStatus(Enum):
    """Status of a vision-based workflow operation."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PANEL_NOT_FOUND = "panel_not_found"
    BUTTON_NOT_FOUND = "button_not_found"
    VERIFICATION_FAILED = "verification_failed"
    NOT_AVAILABLE = "not_available"


@dataclass
class VisionWorkflowResult:
    """
    Result of a vision-based workflow operation.

    This is the standard return type for high-level vision-based workflow
    methods like add_building_block(), run_project_setup_fix_all(), etc.
    """
    success: bool
    status: VisionWorkflowStatus
    message: str
    duration_ms: int = 0
    details: Optional[dict] = None
    error: Optional[str] = None
    screenshot_before: Optional[bytes] = None
    screenshot_after: Optional[bytes] = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "success": self.success,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "error": self.error,
            "has_screenshot_before": self.screenshot_before is not None,
            "has_screenshot_after": self.screenshot_after is not None,
        }


@dataclass
class PanelStateResult:
    """
    Result of checking panel state including errors and warnings.

    Used by verify_panel_state() to return comprehensive panel state information.
    """
    panel_found: bool
    panel_name: str
    has_errors: bool = False
    has_warnings: bool = False
    error_count: int = 0
    warning_count: int = 0
    error_messages: Optional[List[str]] = None
    warning_messages: Optional[List[str]] = None
    panel_bounds: Optional[dict] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.error_messages is None:
            self.error_messages = []
        if self.warning_messages is None:
            self.warning_messages = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "panel_found": self.panel_found,
            "panel_name": self.panel_name,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "error_messages": self.error_messages,
            "warning_messages": self.warning_messages,
            "panel_bounds": self.panel_bounds,
            "error": self.error,
        }


@dataclass
class BuildProgressInfo:
    """
    Information about APK build progress.

    Used by build_apk() to track build progress and provide detailed status.
    """
    phase: str  # Current build phase (compiling, packaging, signing, etc.)
    progress_percent: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining: Optional[float] = None
    current_task: Optional[str] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "phase": self.phase,
            "progress_percent": self.progress_percent,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining": self.estimated_remaining,
            "current_task": self.current_task,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# =============================================================================
# Dialog Handling Types
# =============================================================================


class DialogType(Enum):
    """Types of Unity dialogs that can be detected and handled."""
    INPUT_SYSTEM = "input_system"           # "Enable new Input System?" prompt
    API_UPDATE = "api_update"               # "API Update Required" dialog
    RESTART_EDITOR = "restart_editor"       # "Restart Editor?" prompt
    SAFE_MODE = "safe_mode"                 # "Enter Safe Mode?" dialog
    BUILD_FAILED = "build_failed"           # "Build Failed" dialog
    IMPORT = "import"                       # Package import dialog
    SCRIPT_RELOAD = "script_reload"         # Script reload confirmation
    SAVE_SCENE = "save_scene"               # "Save current scene?" prompt
    ASSET_IMPORT_OVERWRITE = "asset_import_overwrite"  # Asset overwrite confirmation
    UNKNOWN = "unknown"                     # Unknown dialog type


class DialogAction(Enum):
    """Actions that can be taken on dialogs."""
    ACCEPT = "accept"       # Click Yes/OK/Accept/Continue
    REJECT = "reject"       # Click No/Cancel/Reject
    DISMISS = "dismiss"     # Click Close/X or press Escape
    IGNORE = "ignore"       # Don't handle this dialog
    CUSTOM = "custom"       # Custom button to click


@dataclass
class DialogConfig:
    """Configuration for how to handle a specific dialog type.

    This allows customizing automatic dialog handling behavior.

    Example:
        # Accept Input System dialogs, reject Safe Mode dialogs
        config = DialogConfig(
            dialog_type=DialogType.INPUT_SYSTEM,
            action=DialogAction.ACCEPT,
            enabled=True,
            log_handling=True
        )
    """
    dialog_type: DialogType
    action: DialogAction = DialogAction.ACCEPT
    enabled: bool = True
    log_handling: bool = True
    custom_button: Optional[str] = None  # Used when action is CUSTOM
    wait_after_handle: float = 1.0       # Seconds to wait after handling


@dataclass
class DialogHandleResult:
    """Result of attempting to handle a dialog."""
    dialog_type: DialogType
    detected: bool = False
    handled: bool = False
    action_taken: Optional[DialogAction] = None
    error_message: Optional[str] = None
    window_title: Optional[str] = None
    timestamp: Optional[str] = None

    def __str__(self) -> str:
        if self.handled:
            return f"Dialog {self.dialog_type.value}: handled with {self.action_taken.value if self.action_taken else 'unknown'}"
        elif self.detected:
            return f"Dialog {self.dialog_type.value}: detected but not handled"
        else:
            return f"Dialog {self.dialog_type.value}: not detected"


@dataclass
class DialogLog:
    """Log entry for a handled dialog."""
    dialog_type: DialogType
    action: DialogAction
    timestamp: str
    window_title: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class UnityAgent:
    """
    macOS automation agent specialized for Unity Editor.

    Provides methods to detect Unity state, navigate menus,
    interact with windows, and automate common workflows.

    Example:
        agent = UnityAgent()

        # Check if Unity is running
        if agent.is_unity_running():
            # Open Build Settings
            agent.navigate_menu("File", "Build Settings...")
    """

    # Unity process and window patterns
    UNITY_BUNDLE_ID = "com.unity3d.UnityEditor5.x"
    UNITY_PROCESS_NAME = "Unity"
    UNITY_WINDOW_TITLE_PATTERN = r"^(.+) - (.+) - Unity (\d+\.\d+\.\d+[a-z0-9]*).*$"

    # Timing constants (in seconds)
    MENU_ANIMATION_DELAY = 0.3
    WINDOW_OPEN_DELAY = 0.5
    KEYSTROKE_DELAY = 0.05

    def __init__(
        self,
        enable_vision_fallback: bool = True,
        enable_log_monitoring: bool = True,
        enable_dialog_registry: bool = True,
        dialog_registry_path: Optional[str] = None,
    ):
        """
        Initialize the Unity automation agent.

        Args:
            enable_vision_fallback: If True, click operations can fall back to
                                   vision-based element detection when AppleScript fails.
            enable_log_monitoring: If True, use log-based build monitoring for more
                                  accurate build status detection.
            enable_dialog_registry: If True, load YAML-configurable dialog handlers
                                   from .claude-loop/dialog-handlers.yaml.
            dialog_registry_path: Optional custom path for dialog handlers YAML file.
        """
        self._cached_state: Optional[UnityState] = None
        self._state_cache_time: float = 0
        self._state_cache_ttl: float = 2.0  # Cache state for 2 seconds
        self._dialog_configs: dict = self._get_default_dialog_configs()
        self._dialog_log: List[DialogLog] = []
        self._enable_vision_fallback = enable_vision_fallback
        self._click_helper: Optional[Any] = None  # ClickHelper when available

        # Multi-monitor screenshot capture
        self._screenshot_capture: Optional[Any] = None  # MultiMonitorCapture when available
        self._enable_multi_monitor = SCREENSHOT_AVAILABLE

        # Log-based build monitoring
        self._enable_log_monitoring = enable_log_monitoring and LOG_MONITOR_AVAILABLE
        self._log_monitor: Optional[Any] = None  # UnityLogMonitor when available
        self._build_progress_callback: Optional[Callable[[float, str], None]] = None

        # YAML-configurable dialog registry
        self._enable_dialog_registry = enable_dialog_registry and DIALOG_REGISTRY_AVAILABLE
        self._dialog_registry: Optional[Any] = None  # DialogRegistry when available
        self._dialog_registry_path = dialog_registry_path
        if self._enable_dialog_registry:
            self._init_dialog_registry()

    # =========================================================================
    # Unity App Detection
    # =========================================================================

    def is_unity_running(self) -> bool:
        """
        Check if Unity Editor is currently running.

        Returns:
            True if Unity is running, False otherwise.
        """
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.UNITY_PROCESS_NAME],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def get_unity_pid(self) -> Optional[int]:
        """
        Get the process ID of the running Unity Editor.

        Returns:
            Process ID if Unity is running, None otherwise.
        """
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.UNITY_PROCESS_NAME],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                return int(pids[0]) if pids else None
        except (subprocess.SubprocessError, ValueError):
            pass
        return None

    def get_open_project(self) -> Optional[UnityProject]:
        """
        Get information about the currently open Unity project.

        Parses the Unity window title to extract project name, path, and version.

        Returns:
            UnityProject if a project is open, None otherwise.
        """
        window_title = self._get_unity_window_title()
        if not window_title:
            return None

        # Parse window title: "ProjectName - /path/to/project - Unity 2022.3.1f1 <DX11>"
        match = re.match(self.UNITY_WINDOW_TITLE_PATTERN, window_title)
        if match:
            return UnityProject(
                name=match.group(1).strip(),
                path=match.group(2).strip(),
                version=match.group(3).strip()
            )

        # Fallback: try simpler pattern for different Unity versions
        if " - Unity " in window_title:
            parts = window_title.split(" - ")
            if len(parts) >= 2:
                return UnityProject(
                    name=parts[0].strip(),
                    path=parts[1].strip() if len(parts) > 2 else "",
                    version=None
                )

        return None

    def get_state(self, force_refresh: bool = False) -> UnityState:
        """
        Get the current state of Unity Editor.

        Uses caching to avoid repeated expensive AppleScript calls.

        Args:
            force_refresh: If True, bypass cache and refresh state.

        Returns:
            Current UnityState.
        """
        current_time = time.time()

        if (not force_refresh and
            self._cached_state is not None and
            current_time - self._state_cache_time < self._state_cache_ttl):
            return self._cached_state

        is_running = self.is_unity_running()

        if not is_running:
            self._cached_state = UnityState(is_running=False)
        else:
            self._cached_state = UnityState(
                is_running=True,
                project=self.get_open_project(),
                active_window=self._get_active_window_name(),
                visible_windows=self.get_visible_windows()
            )

        self._state_cache_time = current_time
        return self._cached_state

    # =========================================================================
    # Unity Window Detection
    # =========================================================================

    def get_visible_windows(self) -> List[str]:
        """
        Get list of visible Unity windows/tabs.

        Returns:
            List of window names that are currently visible.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                set windowList to {}
                repeat with w in windows
                    set end of windowList to name of w
                end repeat
                return windowList
            end tell
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse AppleScript list output
                output = result.stdout.strip()
                if output:
                    # Remove outer braces and split by comma
                    windows = [w.strip() for w in output.split(',')]
                    return windows
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

        return []

    def is_window_visible(self, window: UnityWindow) -> bool:
        """
        Check if a specific Unity window is visible.

        Args:
            window: The Unity window to check.

        Returns:
            True if the window is visible, False otherwise.
        """
        visible = self.get_visible_windows()
        return any(window.value.lower() in w.lower() for w in visible)

    def focus_window(self, window: UnityWindow) -> bool:
        """
        Bring a Unity window to focus.

        Args:
            window: The Unity window to focus.

        Returns:
            True if successful, False otherwise.
        """
        # First ensure Unity is in focus
        if not self._activate_unity():
            return False

        # Use Window menu to focus specific window
        return self.navigate_menu("Window", "General", window.value)

    # =========================================================================
    # Unity State Detection
    # =========================================================================

    def is_compiling(self) -> bool:
        """
        Check if Unity is currently compiling scripts.

        Detects compilation by checking for "Compiling" in the Unity window title
        or status bar. This is useful for waiting before performing other operations.

        Returns:
            True if scripts are compiling, False otherwise.

        Example:
            if agent.is_compiling():
                print("Unity is compiling scripts...")
                agent.wait_for_idle()
        """
        return self._is_compiling()

    def is_importing(self) -> bool:
        """
        Check if Unity is currently importing assets.

        Detects import operations by checking for import progress indicators,
        "Importing" text in windows, or progress bars.

        Returns:
            True if assets are importing, False otherwise.

        Example:
            if agent.is_importing():
                print("Unity is importing assets...")
                agent.wait_for_idle()
        """
        return self._is_importing()

    def is_in_play_mode(self) -> bool:
        """
        Check if Unity Editor is in Play mode.

        Play mode is detected by checking the Game window's play/pause button state
        or the editor toolbar.

        Returns:
            True if Play mode is active, False otherwise.

        Example:
            if agent.is_in_play_mode():
                print("Unity is in play mode")
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Check window title for play mode indicators
                    set mainWindow to window 1
                    set windowName to name of mainWindow
                    -- Unity adds a special indicator when in play mode
                    -- The window title often shows play state or game view is active
                    if windowName contains "▶" or windowName contains "Play" then
                        return "yes"
                    end if

                    -- Check for pause button in toolbar (only visible in play mode)
                    try
                        set toolbars to every toolbar of mainWindow
                        repeat with tb in toolbars
                            if exists button "Pause" of tb then
                                -- If Pause button is enabled, we're in play mode
                                if enabled of button "Pause" of tb then
                                    return "yes"
                                end if
                            end if
                        end repeat
                    end try

                    -- Alternative: Check Game window state
                    try
                        repeat with w in windows
                            if name of w contains "Game" then
                                -- Check for play controls in game window
                                set gameWindow to w
                                try
                                    if exists button 1 of toolbar 1 of gameWindow then
                                        set btnName to name of button 1 of toolbar 1 of gameWindow
                                        if btnName is "Stop" or btnName is "Pause" then
                                            return "yes"
                                        end if
                                    end if
                                end try
                            end if
                        end repeat
                    end try

                    return "no"
                on error errMsg
                    return "no"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def has_console_errors(self) -> bool:
        """
        Check if the Unity Console has any error messages.

        Opens the Console window if needed and checks for error indicators.
        This is useful for detecting compilation errors, runtime exceptions,
        or other issues.

        Returns:
            True if there are errors in the Console, False otherwise.

        Example:
            if agent.has_console_errors():
                errors = agent.get_console_messages(ConsoleMessageLevel.ERROR)
                for error in errors:
                    print(f"Error: {error.message}")
        """
        error_count = self._get_console_error_count()
        return error_count > 0

    def get_console_messages(
        self,
        level: Optional[ConsoleMessageLevel] = None,
        max_messages: int = 100
    ) -> List[ConsoleMessage]:
        """
        Get messages from the Unity Console window.

        Opens the Console window if needed and reads the visible messages.
        Can filter by message level (Log, Warning, Error, etc.).

        Args:
            level: Filter by message level (None for all messages)
            max_messages: Maximum number of messages to return (default 100)

        Returns:
            List of ConsoleMessage objects.

        Example:
            # Get all errors
            errors = agent.get_console_messages(ConsoleMessageLevel.ERROR)

            # Get all warnings and errors
            issues = agent.get_console_messages()
            issues = [m for m in issues if m.level in (ConsoleMessageLevel.WARNING, ConsoleMessageLevel.ERROR)]
        """
        messages = []

        # Ensure Console window is visible
        if not self.is_window_visible(UnityWindow.CONSOLE):
            # Try to open Console via menu
            self.navigate_menu("Window", "General", "Console")
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Get console content via AppleScript
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set consoleContent to ""

                    -- Find Console window
                    repeat with w in windows
                        if name of w contains "Console" then
                            set consoleWindow to w

                            -- Try to get text from scroll area
                            try
                                repeat with scrollArea in scroll areas of consoleWindow
                                    try
                                        set textContent to value of text area 1 of scrollArea
                                        set consoleContent to consoleContent & textContent & "\\n"
                                    end try
                                    -- Also try static texts
                                    repeat with st in static texts of scrollArea
                                        try
                                            set consoleContent to consoleContent & (value of st) & "\\n"
                                        end try
                                    end repeat
                                end repeat
                            end try

                            -- Try to get from list/table
                            try
                                repeat with tbl in tables of consoleWindow
                                    repeat with row in rows of tbl
                                        try
                                            set rowText to value of static text 1 of row
                                            set consoleContent to consoleContent & rowText & "\\n"
                                        end try
                                    end repeat
                                end repeat
                            end try

                            exit repeat
                        end if
                    end repeat

                    return consoleContent
                on error errMsg
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success or not output:
            return messages

        # Parse console output into messages
        lines = output.strip().split('\n')
        for line in lines[:max_messages]:
            line = line.strip()
            if not line:
                continue

            # Determine message level based on content
            msg_level = ConsoleMessageLevel.LOG
            lower_line = line.lower()

            if 'error' in lower_line or 'exception' in lower_line or 'failed' in lower_line:
                if 'exception' in lower_line:
                    msg_level = ConsoleMessageLevel.EXCEPTION
                else:
                    msg_level = ConsoleMessageLevel.ERROR
            elif 'warning' in lower_line or 'warn' in lower_line:
                msg_level = ConsoleMessageLevel.WARNING
            elif 'assert' in lower_line:
                msg_level = ConsoleMessageLevel.ASSERT

            # Filter by level if specified
            if level is not None and msg_level != level:
                continue

            messages.append(ConsoleMessage(
                message=line,
                level=msg_level
            ))

        return messages

    def wait_for_idle(self, timeout: float = 120.0) -> Tuple[bool, str]:
        """
        Wait until Unity is idle (no compilation, import, or progress).

        This is the primary method for ensuring Unity is ready before
        performing operations. It waits until:
        - No scripts are compiling
        - No assets are importing
        - No progress bars are visible

        Args:
            timeout: Maximum time to wait in seconds (default 120s)

        Returns:
            Tuple of (success, message).
            - success: True if Unity became idle, False if timeout
            - message: Status message describing the result

        Example:
            # Wait for Unity to be ready before building
            success, msg = agent.wait_for_idle(timeout=300)
            if success:
                agent.build("/path/to/build")
            else:
                print(f"Timeout: {msg}")
        """
        start_time = time.time()
        last_status = ""

        # Brief initial delay
        time.sleep(0.3)

        while time.time() - start_time < timeout:
            is_compiling = self._is_compiling()
            is_importing = self._is_importing()

            current_status = []
            if is_compiling:
                current_status.append("compiling")
            if is_importing:
                current_status.append("importing")

            status_str = ", ".join(current_status) if current_status else "idle"

            # Log status changes
            if status_str != last_status:
                last_status = status_str

            # Check if idle
            if not is_compiling and not is_importing:
                # Double-check after brief pause
                time.sleep(0.5)
                if not self._is_compiling() and not self._is_importing():
                    elapsed = time.time() - start_time
                    return (True, f"Unity is idle after {elapsed:.1f}s")

            time.sleep(0.5)

        return (False, f"Timeout after {timeout}s waiting for Unity to become idle")

    def get_editor_state(self) -> EditorState:
        """
        Get comprehensive state of the Unity Editor.

        Returns a snapshot of the current editor state including:
        - Compilation status
        - Import status
        - Play mode status
        - Console error/warning counts

        Returns:
            EditorState object with current state information.

        Example:
            state = agent.get_editor_state()
            if state.has_errors:
                print(f"Console has {state.console_error_count} errors")
            if state.is_compiling:
                print("Scripts are compiling...")
        """
        error_count = self._get_console_error_count()
        warning_count = self._get_console_warning_count()

        return EditorState(
            is_compiling=self._is_compiling(),
            is_importing=self._is_importing(),
            is_playing=self.is_in_play_mode(),
            has_errors=error_count > 0,
            console_error_count=error_count,
            console_warning_count=warning_count
        )

    # =========================================================================
    # Unity State Detection Internal Helpers
    # =========================================================================

    def _get_console_error_count(self) -> int:
        """
        Get the count of error messages in the Console.

        Returns:
            Number of error messages (0 if unable to determine).
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set errorCount to 0

                    -- Find Console window
                    repeat with w in windows
                        if name of w contains "Console" then
                            set consoleWindow to w

                            -- Look for error count in toolbar buttons or badges
                            try
                                repeat with btn in buttons of toolbar 1 of consoleWindow
                                    set btnName to name of btn
                                    -- Error button often shows count like "123 Errors"
                                    if btnName contains "Error" then
                                        try
                                            set countMatch to do shell script "echo " & quoted form of btnName & " | grep -oE '[0-9]+' | head -1"
                                            if countMatch is not "" then
                                                set errorCount to countMatch as integer
                                                exit repeat
                                            end if
                                        end try
                                    end if
                                end repeat
                            end try

                            -- Alternative: Check badge on error icon
                            try
                                repeat with grp in groups of consoleWindow
                                    repeat with st in static texts of grp
                                        set stValue to value of st
                                        try
                                            set numVal to stValue as integer
                                            -- This might be an error count badge
                                            if numVal > 0 then
                                                set errorCount to numVal
                                            end if
                                        end try
                                    end repeat
                                end repeat
                            end try

                            exit repeat
                        end if
                    end repeat

                    return errorCount as text
                on error errMsg
                    return "0"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        try:
            return int(output) if success else 0
        except ValueError:
            return 0

    def _get_console_warning_count(self) -> int:
        """
        Get the count of warning messages in the Console.

        Returns:
            Number of warning messages (0 if unable to determine).
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set warningCount to 0

                    -- Find Console window
                    repeat with w in windows
                        if name of w contains "Console" then
                            set consoleWindow to w

                            -- Look for warning count in toolbar buttons
                            try
                                repeat with btn in buttons of toolbar 1 of consoleWindow
                                    set btnName to name of btn
                                    if btnName contains "Warning" then
                                        try
                                            set countMatch to do shell script "echo " & quoted form of btnName & " | grep -oE '[0-9]+' | head -1"
                                            if countMatch is not "" then
                                                set warningCount to countMatch as integer
                                                exit repeat
                                            end if
                                        end try
                                    end if
                                end repeat
                            end try

                            exit repeat
                        end if
                    end repeat

                    return warningCount as text
                on error errMsg
                    return "0"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        try:
            return int(output) if success else 0
        except ValueError:
            return 0

    def _get_status_bar_text(self) -> str:
        """
        Get the text from Unity's status bar.

        The status bar shows current activity like "Compiling Scripts...",
        "Importing Assets...", etc.

        Returns:
            Status bar text or empty string.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set mainWindow to window 1
                    set statusText to ""

                    -- Look for status bar elements
                    -- Unity's status bar is usually at the bottom
                    try
                        repeat with st in static texts of mainWindow
                            set stValue to value of st
                            if stValue contains "Compiling" or stValue contains "Importing" or stValue contains "Progress" or stValue contains "Loading" then
                                set statusText to stValue
                                exit repeat
                            end if
                        end repeat
                    end try

                    -- Also check groups in the main window
                    try
                        repeat with grp in groups of mainWindow
                            repeat with st in static texts of grp
                                set stValue to value of st
                                if stValue contains "Compiling" or stValue contains "Importing" or stValue contains "Progress" then
                                    set statusText to stValue
                                    exit repeat
                                end if
                            end repeat
                        end repeat
                    end try

                    return statusText
                on error errMsg
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return output if success else ""

    # =========================================================================
    # Unity Package Manager Automation
    # =========================================================================

    def open_package_manager(self) -> bool:
        """
        Open the Unity Package Manager window.

        Uses Window > Package Manager menu navigation.

        Returns:
            True if Package Manager was opened, False otherwise.
        """
        success = self.navigate_menu("Window", "Package Manager")
        if success:
            time.sleep(self.WINDOW_OPEN_DELAY)
            # Invalidate cache since we changed window state
            self._cached_state = None
        return success

    def wait_for_package_import(self, timeout: float = 120.0) -> Tuple[bool, str]:
        """
        Wait for Unity to finish importing packages.

        Monitors Unity's progress/busy state until idle or timeout.

        Args:
            timeout: Maximum time to wait in seconds (default 120s).

        Returns:
            Tuple of (success, message).
        """
        start_time = time.time()
        poll_interval = 2.0
        last_status = ""

        while time.time() - start_time < timeout:
            is_importing = self._is_importing()
            is_compiling = self._is_compiling()

            current_status = f"importing={is_importing}, compiling={is_compiling}"
            if current_status != last_status:
                last_status = current_status

            if not is_importing and not is_compiling:
                # Double check with a short delay
                time.sleep(0.5)
                if not self._is_importing() and not self._is_compiling():
                    return (True, "Import completed successfully")

            time.sleep(poll_interval)

        return (False, f"Timeout after {timeout} seconds waiting for import")

    def search_package(self, query: str) -> bool:
        """
        Search for a package in the Package Manager.

        Requires Package Manager window to be open.

        Args:
            query: The search query string.

        Returns:
            True if search was initiated, False otherwise.
        """
        # First ensure Package Manager is visible
        if not self.is_window_visible(UnityWindow.PACKAGE_MANAGER):
            if not self.open_package_manager():
                return False
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Focus the search field and type the query
        # Package Manager search is typically focused via keyboard shortcut
        # Cmd+F or clicking the search field
        script = '''
        tell application "System Events"
            tell process "Unity"
                -- Focus search field with Cmd+K (Package Manager search shortcut)
                keystroke "k" using command down
                delay 0.3
                -- Clear any existing text and type new query
                keystroke "a" using command down
                delay 0.1
        '''
        script += f'''
                keystroke "{query}"
                delay 0.5
            end tell
        end tell
        '''

        success, _ = self._run_applescript(script)
        return success

    def install_package_from_asset_store(self, package_name: str) -> Tuple[bool, str]:
        """
        Install a package from My Assets in the Package Manager.

        Searches for the package in My Assets and installs it.

        Args:
            package_name: Name of the package to install.

        Returns:
            Tuple of (success, message).
        """
        # Open Package Manager if not open
        if not self.is_window_visible(UnityWindow.PACKAGE_MANAGER):
            if not self.open_package_manager():
                return (False, "Failed to open Package Manager")
            time.sleep(1.0)

        # Switch to My Assets registry
        if not self._switch_package_registry("my_assets"):
            return (False, "Failed to switch to My Assets")
        time.sleep(1.0)

        # Search for the package
        if not self.search_package(package_name):
            return (False, f"Failed to search for package: {package_name}")
        time.sleep(1.0)

        # Try to find and click the package in results, then click Install/Import
        success = self._click_package_in_list(package_name)
        if not success:
            return (False, f"Package not found in search results: {package_name}")
        time.sleep(0.5)

        # Click Download/Import button (Asset Store packages show Download first, then Import)
        if self._click_package_button("Download"):
            # Wait for download
            download_success, msg = self._wait_for_download(timeout=300.0)
            if not download_success:
                return (False, f"Download failed: {msg}")
            # After download, click Import
            time.sleep(1.0)

        # Try to click Import button
        if self._click_package_button("Import"):
            time.sleep(0.5)
            # Handle import dialog if it appears
            self._handle_import_dialog()
            return (True, f"Started importing {package_name}")

        return (False, f"Could not find Install/Import button for {package_name}")

    def get_package_status(self, package_id: str) -> PackageInfo:
        """
        Check the status of a package.

        Args:
            package_id: The package identifier (e.g., "com.meta.xr.sdk.core").

        Returns:
            PackageInfo with current status.
        """
        # Check manifest.json for installed packages
        project = self.get_open_project()
        if project and project.path:
            manifest_path = f"{project.path}/Packages/manifest.json"
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    dependencies = manifest.get("dependencies", {})
                    if package_id in dependencies:
                        return PackageInfo(
                            name=package_id,
                            package_id=package_id,
                            version=dependencies[package_id],
                            status=PackageStatus.INSTALLED,
                            source=PackageSource.UNITY_REGISTRY
                        )
            except (FileNotFoundError, json.JSONDecodeError, PermissionError):
                pass

        # Package not found in manifest
        return PackageInfo(
            name=package_id,
            package_id=package_id,
            status=PackageStatus.NOT_FOUND
        )

    def handle_package_dialogs(self) -> List[str]:
        """
        Handle common package-related dialogs.

        Checks for and handles:
        - Input System restart prompt
        - API Update Required dialog
        - Editor restart dialog

        Returns:
            List of dialog types that were handled.
        """
        handled = []

        # Check for Input System dialog
        if self._handle_input_system_dialog():
            handled.append("input_system")

        # Check for API update dialog
        if self._handle_api_update_dialog():
            handled.append("api_update")

        # Check for restart dialog
        if self._handle_restart_dialog():
            handled.append("restart")

        return handled

    def get_import_progress(self) -> Tuple[bool, float, str]:
        """
        Get the current import progress if importing.

        Returns:
            Tuple of (is_importing, progress_percentage, status_message).
        """
        is_importing = self._is_importing()
        if not is_importing:
            return (False, 100.0, "Idle")

        # Try to read progress from Unity's progress bar
        progress, status = self._get_progress_bar_info()
        return (True, progress, status)

    # =========================================================================
    # Dialog Handling System
    # =========================================================================

    def _get_default_dialog_configs(self) -> dict:
        """Get the default dialog handling configurations."""
        return {
            DialogType.INPUT_SYSTEM: DialogConfig(
                dialog_type=DialogType.INPUT_SYSTEM,
                action=DialogAction.ACCEPT,
                enabled=True,
                log_handling=True,
                wait_after_handle=2.0  # Input system change needs restart wait
            ),
            DialogType.API_UPDATE: DialogConfig(
                dialog_type=DialogType.API_UPDATE,
                action=DialogAction.ACCEPT,  # "I Made a Backup. Go Ahead!"
                enabled=True,
                log_handling=True,
                wait_after_handle=1.0
            ),
            DialogType.RESTART_EDITOR: DialogConfig(
                dialog_type=DialogType.RESTART_EDITOR,
                action=DialogAction.ACCEPT,
                enabled=True,
                log_handling=True,
                wait_after_handle=5.0  # Editor restart takes time
            ),
            DialogType.SAFE_MODE: DialogConfig(
                dialog_type=DialogType.SAFE_MODE,
                action=DialogAction.REJECT,  # Default: don't enter safe mode
                enabled=True,
                log_handling=True,
                wait_after_handle=1.0
            ),
            DialogType.BUILD_FAILED: DialogConfig(
                dialog_type=DialogType.BUILD_FAILED,
                action=DialogAction.DISMISS,
                enabled=True,
                log_handling=True,
                wait_after_handle=0.5
            ),
            DialogType.IMPORT: DialogConfig(
                dialog_type=DialogType.IMPORT,
                action=DialogAction.ACCEPT,  # Import all
                enabled=True,
                log_handling=True,
                wait_after_handle=1.0
            ),
            DialogType.SAVE_SCENE: DialogConfig(
                dialog_type=DialogType.SAVE_SCENE,
                action=DialogAction.ACCEPT,  # Save before proceeding
                enabled=True,
                log_handling=True,
                wait_after_handle=1.0
            ),
            DialogType.SCRIPT_RELOAD: DialogConfig(
                dialog_type=DialogType.SCRIPT_RELOAD,
                action=DialogAction.ACCEPT,
                enabled=True,
                log_handling=True,
                wait_after_handle=2.0
            ),
        }

    def configure_dialog_handler(
        self,
        dialog_type: DialogType,
        action: Optional[DialogAction] = None,
        enabled: Optional[bool] = None,
        log_handling: Optional[bool] = None,
        custom_button: Optional[str] = None,
        wait_after_handle: Optional[float] = None
    ) -> None:
        """
        Configure how a specific dialog type is handled.

        Args:
            dialog_type: The type of dialog to configure.
            action: The action to take when this dialog appears.
            enabled: Whether to handle this dialog type.
            log_handling: Whether to log when this dialog is handled.
            custom_button: Button name to click (for CUSTOM action).
            wait_after_handle: Seconds to wait after handling.

        Example:
            # Disable automatic handling of Safe Mode dialogs
            agent.configure_dialog_handler(
                DialogType.SAFE_MODE,
                enabled=False
            )

            # Click a custom button for Input System dialog
            agent.configure_dialog_handler(
                DialogType.INPUT_SYSTEM,
                action=DialogAction.CUSTOM,
                custom_button="Both"
            )
        """
        if dialog_type not in self._dialog_configs:
            self._dialog_configs[dialog_type] = DialogConfig(dialog_type=dialog_type)

        config = self._dialog_configs[dialog_type]
        if action is not None:
            config.action = action
        if enabled is not None:
            config.enabled = enabled
        if log_handling is not None:
            config.log_handling = log_handling
        if custom_button is not None:
            config.custom_button = custom_button
        if wait_after_handle is not None:
            config.wait_after_handle = wait_after_handle

    def get_dialog_config(self, dialog_type: DialogType) -> DialogConfig:
        """
        Get the current configuration for a dialog type.

        Args:
            dialog_type: The type of dialog to get configuration for.

        Returns:
            The DialogConfig for the specified type.
        """
        if dialog_type not in self._dialog_configs:
            return DialogConfig(dialog_type=dialog_type)
        return self._dialog_configs[dialog_type]

    def detect_dialog(self) -> Optional[DialogType]:
        """
        Detect if any Unity dialog is currently open.

        Returns:
            DialogType if a dialog is detected, None otherwise.

        Example:
            dialog = agent.detect_dialog()
            if dialog:
                print(f"Found dialog: {dialog.value}")
        """
        dialog_type, _ = self._detect_dialog()
        return dialog_type

    def handle_dialog(
        self,
        dialog_type: Optional[DialogType] = None,
        force_action: Optional[DialogAction] = None,
        use_registry: Optional[bool] = None
    ) -> DialogHandleResult:
        """
        Handle a specific dialog or auto-detect and handle.

        If the dialog registry is enabled and configured, dialogs can be handled
        using YAML-configurable patterns from .claude-loop/dialog-handlers.yaml.

        Args:
            dialog_type: Specific dialog to handle, or None to auto-detect.
            force_action: Override the configured action for this call.
            use_registry: If True, try dialog registry first. If None, use default.

        Returns:
            DialogHandleResult with details about what happened.

        Example:
            # Auto-detect and handle any dialog
            result = agent.handle_dialog()
            if result.handled:
                print(f"Handled {result.dialog_type.value}")

            # Handle a specific dialog type
            result = agent.handle_dialog(DialogType.BUILD_FAILED)
        """
        import datetime

        timestamp = datetime.datetime.now().isoformat()

        # Try dialog registry first if enabled
        should_use_registry = (
            use_registry if use_registry is not None
            else self._enable_dialog_registry
        )
        if should_use_registry and dialog_type is None:
            registry_result = self._handle_dialog_with_registry()
            if registry_result is not None:
                return registry_result

        # Auto-detect dialog if not specified
        if dialog_type is None:
            detected_type, window_title = self._detect_dialog()
            if detected_type is None:
                return DialogHandleResult(
                    dialog_type=DialogType.UNKNOWN,
                    detected=False,
                    handled=False,
                    timestamp=timestamp
                )
            dialog_type = detected_type
        else:
            _, window_title = self._detect_dialog()

        # Get configuration
        config = self.get_dialog_config(dialog_type)

        # Check if handling is enabled
        if not config.enabled:
            return DialogHandleResult(
                dialog_type=dialog_type,
                detected=True,
                handled=False,
                error_message="Dialog handling disabled for this type",
                window_title=window_title,
                timestamp=timestamp
            )

        # Determine action
        action = force_action if force_action else config.action

        # Handle the dialog
        handled = False
        error_message = None

        if dialog_type == DialogType.INPUT_SYSTEM:
            handled = self._handle_input_system_dialog()
        elif dialog_type == DialogType.API_UPDATE:
            handled = self._handle_api_update_dialog()
        elif dialog_type == DialogType.RESTART_EDITOR:
            handled = self._handle_restart_dialog()
        elif dialog_type == DialogType.SAFE_MODE:
            accept = action in (DialogAction.ACCEPT, DialogAction.CUSTOM)
            handled, error_message = self._handle_safe_mode_dialog(accept=accept)
        elif dialog_type == DialogType.BUILD_FAILED:
            handled, error_message = self._handle_build_failed_dialog()
        elif dialog_type == DialogType.IMPORT:
            handled = self._handle_import_dialog()
        elif action == DialogAction.CUSTOM and config.custom_button:
            handled = self._click_button(config.custom_button)
        else:
            # Generic button click based on action
            button_map = {
                DialogAction.ACCEPT: ["Yes", "OK", "Accept", "Continue", "Import"],
                DialogAction.REJECT: ["No", "Cancel", "Reject"],
                DialogAction.DISMISS: ["Close", "OK", "X"],
            }
            buttons = button_map.get(action, [])
            for button in buttons:
                if self._click_button(button):
                    handled = True
                    break

        # Log the handling
        if config.log_handling:
            log_entry = DialogLog(
                dialog_type=dialog_type,
                action=action,
                timestamp=timestamp,
                window_title=window_title,
                success=handled,
                error_message=error_message
            )
            self._dialog_log.append(log_entry)

        # Wait after handling if successful
        if handled and config.wait_after_handle > 0:
            time.sleep(config.wait_after_handle)

        return DialogHandleResult(
            dialog_type=dialog_type,
            detected=True,
            handled=handled,
            action_taken=action,
            error_message=error_message,
            window_title=window_title,
            timestamp=timestamp
        )

    def handle_all_dialogs(
        self,
        max_dialogs: int = 10,
        timeout: float = 30.0
    ) -> List[DialogHandleResult]:
        """
        Handle all detected dialogs until none remain or limits reached.

        This is useful for clearing multiple dialogs that may appear in sequence.

        Args:
            max_dialogs: Maximum number of dialogs to handle.
            timeout: Maximum time in seconds to spend handling dialogs.

        Returns:
            List of DialogHandleResult for each dialog handled.

        Example:
            # Clear all dialogs before starting a build
            results = agent.handle_all_dialogs()
            for r in results:
                print(f"Handled: {r.dialog_type.value}")
        """
        results = []
        start_time = time.time()
        dialogs_handled = 0

        while dialogs_handled < max_dialogs:
            # Check timeout
            if time.time() - start_time > timeout:
                break

            # Try to detect and handle a dialog
            result = self.handle_dialog()

            if not result.detected:
                # No more dialogs
                break

            results.append(result)

            if result.handled:
                dialogs_handled += 1
            else:
                # If we detected but couldn't handle, wait a bit and try again
                time.sleep(0.5)

        return results

    def get_dialog_log(
        self,
        dialog_type: Optional[DialogType] = None,
        limit: int = 100
    ) -> List[DialogLog]:
        """
        Get the log of handled dialogs.

        Args:
            dialog_type: Filter by dialog type, or None for all.
            limit: Maximum number of entries to return.

        Returns:
            List of DialogLog entries, newest first.

        Example:
            # Get all dialog handling history
            log = agent.get_dialog_log()
            for entry in log:
                print(f"{entry.timestamp}: {entry.dialog_type.value} - {entry.action.value}")
        """
        if dialog_type:
            filtered = [e for e in self._dialog_log if e.dialog_type == dialog_type]
        else:
            filtered = self._dialog_log.copy()

        # Return newest first, with limit
        return filtered[-limit:][::-1]

    def clear_dialog_log(self) -> None:
        """Clear the dialog handling log."""
        self._dialog_log.clear()

    def get_build_failure_info(self) -> Tuple[bool, Optional[str]]:
        """
        Check for and capture build failure information.

        This method detects 'Build Failed' dialogs and captures the error message
        before dismissing the dialog.

        Returns:
            Tuple of (dialog_found, error_message).

        Example:
            found, error = agent.get_build_failure_info()
            if found:
                print(f"Build failed: {error}")
        """
        return self._handle_build_failed_dialog()

    # =========================================================================
    # Package Manager Internal Helpers
    # =========================================================================

    def _switch_package_registry(self, registry: str) -> bool:
        """
        Switch the Package Manager to a different registry/source.

        Args:
            registry: One of "unity_registry", "my_assets", "in_project"

        Returns:
            True if successful, False otherwise.
        """
        # The registry dropdown is at the top left of Package Manager
        # We need to click it and select the appropriate option
        registry_names = {
            "unity_registry": "Unity Registry",
            "my_assets": "My Assets",
            "in_project": "In Project"
        }

        target = registry_names.get(registry)
        if not target:
            return False

        # Click dropdown then select option
        script = f'''
        tell application "System Events"
            tell process "Unity"
                -- Click the registry dropdown (first popup button in Package Manager)
                set pmWindow to window "Package Manager"
                -- Try to click a popup button with registry options
                try
                    click pop up button 1 of pmWindow
                    delay 0.3
                    click menu item "{target}" of menu 1 of pop up button 1 of pmWindow
                    return "success"
                end try
                return "failed"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _click_package_in_list(self, package_name: str) -> bool:
        """
        Click on a package in the Package Manager list.

        Args:
            package_name: Name of the package to click.

        Returns:
            True if package was found and clicked, False otherwise.
        """
        # Package name is used implicitly - we assume search was already done
        # with this package name before calling this method
        _ = package_name  # Suppress unused parameter warning

        # Use keyboard navigation after search
        script = '''
        tell application "System Events"
            tell process "Unity"
                -- Press down arrow to select first result
                key code 125
                delay 0.2
                -- Press enter to confirm selection
                key code 36
                return "success"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _click_package_button(self, button_name: str) -> bool:
        """
        Click a button in the Package Manager detail pane.

        Args:
            button_name: Name of the button (e.g., "Install", "Import", "Download")

        Returns:
            True if button was clicked, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set pmWindow to window "Package Manager"
                    click button "{button_name}" of pmWindow
                    return "success"
                on error
                    return "not_found"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _wait_for_download(self, timeout: float = 300.0) -> Tuple[bool, str]:
        """
        Wait for package download to complete.

        Args:
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (success, message).
        """
        start_time = time.time()
        poll_interval = 2.0

        while time.time() - start_time < timeout:
            # Check if Import button appears (download complete)
            if self._is_button_visible("Import"):
                return (True, "Download completed")

            # Check for download error
            if self._has_download_error():
                return (False, "Download error detected")

            time.sleep(poll_interval)

        return (False, f"Download timeout after {timeout} seconds")

    def _is_button_visible(self, button_name: str) -> bool:
        """Check if a button is visible in Package Manager."""
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set pmWindow to window "Package Manager"
                    if exists button "{button_name}" of pmWindow then
                        return "yes"
                    end if
                end try
                return "no"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _has_download_error(self) -> bool:
        """Check if there's a download error in Package Manager."""
        # Look for error indicators in the Package Manager window
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set pmWindow to window "Package Manager"
                    set windowText to entire contents of pmWindow as text
                    if windowText contains "error" or windowText contains "failed" then
                        return "yes"
                    end if
                end try
                return "no"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _handle_import_dialog(self) -> bool:
        """Handle the import selection dialog that appears for Asset Store packages."""
        # The import dialog shows package contents with checkboxes
        # We want to click "Import" to import all
        time.sleep(1.0)

        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Look for Import button in any dialog/sheet
                    repeat with w in windows
                        if exists button "Import" of w then
                            click button "Import" of w
                            return "success"
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _handle_input_system_dialog(self) -> bool:
        """Handle 'Enable new Input System?' dialog."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Input System" or windowName contains "Input Manager" then
                            if exists button "Yes" of w then
                                click button "Yes" of w
                                return "handled"
                            end if
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "handled"

    def _handle_api_update_dialog(self) -> bool:
        """Handle 'API Update Required' dialog."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "API Update" then
                            if exists button "I Made a Backup. Go Ahead!" of w then
                                click button "I Made a Backup. Go Ahead!" of w
                                return "handled"
                            end if
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "handled"

    def _handle_restart_dialog(self) -> bool:
        """Handle 'Restart Editor?' dialog."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Restart" then
                            if exists button "Yes" of w then
                                click button "Yes" of w
                                return "handled"
                            end if
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "handled"

    def _handle_safe_mode_dialog(self, accept: bool = False) -> Tuple[bool, str]:
        """
        Handle 'Enter Safe Mode?' dialog.

        Safe Mode is shown when Unity detects compilation errors on startup.
        Usually we want to reject (not enter safe mode) to allow fixing scripts.

        Args:
            accept: If True, click 'Enter Safe Mode'. If False, click 'Ignore'.

        Returns:
            Tuple of (handled, error_message).
        """
        button_name = "Enter Safe Mode" if accept else "Ignore"

        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Safe Mode" then
                            -- Try the specified button first
                            if exists button "{button_name}" of w then
                                click button "{button_name}" of w
                                return "handled:" & windowName
                            end if
                            -- Fallback buttons
                            if exists button "Continue" of w then
                                click button "Continue" of w
                                return "handled:" & windowName
                            end if
                            if exists button "OK" of w then
                                click button "OK" of w
                                return "handled:" & windowName
                            end if
                            return "found_no_button:" & windowName
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if success and output.startswith("handled:"):
            return (True, "")
        elif success and output.startswith("found_no_button:"):
            return (False, f"Dialog found but no matching button: {output}")
        return (False, "")

    def _handle_build_failed_dialog(self) -> Tuple[bool, Optional[str]]:
        """
        Handle 'Build Failed' dialog and capture error message.

        Returns:
            Tuple of (handled, error_message_if_any).
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Build" and (windowName contains "Failed" or windowName contains "Error") then
                            -- Try to capture error text from the dialog
                            set errorText to ""
                            try
                                set allText to entire contents of w as text
                                set errorText to allText
                            end try

                            -- Click OK/Close to dismiss
                            if exists button "OK" of w then
                                click button "OK" of w
                                return "handled:" & errorText
                            end if
                            if exists button "Close" of w then
                                click button "Close" of w
                                return "handled:" & errorText
                            end if
                            return "found:" & errorText
                        end if
                    end repeat
                end try
                return "no_dialog"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if success and output.startswith("handled:"):
            error_msg = output[8:].strip() if len(output) > 8 else None
            return (True, error_msg)
        elif success and output.startswith("found:"):
            error_msg = output[6:].strip() if len(output) > 6 else None
            return (False, error_msg)
        return (False, None)

    def _handle_dialog_with_registry(self) -> Optional[DialogHandleResult]:
        """
        Try to handle a dialog using the YAML-configurable dialog registry.

        Returns:
            DialogHandleResult if a dialog was matched and handled, None otherwise.
        """
        import datetime

        registry = self._get_dialog_registry()
        if registry is None:
            return None

        # Get dialog window info
        _, window_title = self._detect_dialog()
        if window_title is None:
            return None

        # Try to get dialog content (static text)
        dialog_content = self._get_dialog_content()

        # Try to match using the registry
        try:
            match_result = registry.match_dialog(
                window_title=window_title,
                content=dialog_content
            )

            if match_result is None:
                return None

            # Execute the action
            def click_button_callback(button_name: str) -> bool:
                return self._click_button(button_name)

            def capture_callback() -> Optional[bytes]:
                return self.capture_screenshot()

            action_result = registry.execute_action(
                match_result,
                button_click_callback=click_button_callback,
                screenshot_callback=capture_callback
            )

            timestamp = datetime.datetime.now().isoformat()

            return DialogHandleResult(
                dialog_type=DialogType.UNKNOWN,
                detected=True,
                handled=action_result.success,
                action_taken=DialogAction.CUSTOM,
                error_message=action_result.error_message if not action_result.success else None,
                window_title=window_title,
                timestamp=timestamp
            )

        except Exception as e:
            logger.warning(f"Dialog registry handling failed: {e}")
            return None

    def _get_dialog_content(self) -> Optional[str]:
        """
        Get the text content of the current dialog window.

        Returns:
            Dialog content text, or None if not available.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set dialogWindow to window 1
                    set allTexts to {}
                    repeat with staticText in (every static text of dialogWindow)
                        set end of allTexts to (value of staticText)
                    end repeat
                    return allTexts as text
                on error
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if success and output:
            return output
        return None

    def _detect_dialog(self) -> Tuple[Optional[DialogType], Optional[str]]:
        """
        Detect any open dialog and identify its type.

        Returns:
            Tuple of (DialogType if detected, window_title if found).
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        -- Return the window name for the first dialog-like window
                        if windowName contains "Input System" then
                            return "input_system:" & windowName
                        else if windowName contains "API Update" then
                            return "api_update:" & windowName
                        else if windowName contains "Restart" then
                            return "restart:" & windowName
                        else if windowName contains "Safe Mode" then
                            return "safe_mode:" & windowName
                        else if windowName contains "Build" and windowName contains "Failed" then
                            return "build_failed:" & windowName
                        else if windowName contains "Import" and not windowName contains "Package Manager" then
                            return "import:" & windowName
                        else if windowName contains "Save" and windowName contains "Scene" then
                            return "save_scene:" & windowName
                        else if windowName contains "Script" and windowName contains "Reload" then
                            return "script_reload:" & windowName
                        end if
                    end repeat
                end try
                return "none"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success or output == "none":
            return (None, None)

        # Parse the result
        if ":" in output:
            dialog_type_str, window_title = output.split(":", 1)
            type_mapping = {
                "input_system": DialogType.INPUT_SYSTEM,
                "api_update": DialogType.API_UPDATE,
                "restart": DialogType.RESTART_EDITOR,
                "safe_mode": DialogType.SAFE_MODE,
                "build_failed": DialogType.BUILD_FAILED,
                "import": DialogType.IMPORT,
                "save_scene": DialogType.SAVE_SCENE,
                "script_reload": DialogType.SCRIPT_RELOAD,
            }
            return (type_mapping.get(dialog_type_str, DialogType.UNKNOWN), window_title)

        return (DialogType.UNKNOWN, output)

    def _is_importing(self) -> bool:
        """Check if Unity is currently importing assets."""
        # Check for progress bar or "Importing" in status
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Check window titles for import progress
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Importing" or windowName contains "Import" then
                            return "yes"
                        end if
                    end repeat
                    -- Check for progress dialog
                    if exists progress indicator 1 of window 1 then
                        return "yes"
                    end if
                end try
                return "no"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _is_compiling(self) -> bool:
        """Check if Unity is currently compiling scripts."""
        # Unity shows "Compiling..." in the status bar or window
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Check for compilation indicator in main window
                    set mainWindow to window 1
                    set windowName to name of mainWindow
                    if windowName contains "Compiling" then
                        return "yes"
                    end if
                end try
                return "no"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _get_progress_bar_info(self) -> Tuple[float, str]:
        """Get progress bar information if visible."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set prog to progress indicator 1 of window 1
                    set progValue to value of prog
                    return progValue as text
                end try
                return "0"
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        try:
            progress = float(output) if success else 0.0
            return (progress, "Importing...")
        except ValueError:
            return (0.0, "Unknown")

    # =========================================================================
    # Unity Project Settings Automation
    # =========================================================================

    def open_project_settings(self) -> bool:
        """
        Open the Unity Project Settings window.

        Uses Edit > Project Settings menu navigation.

        Returns:
            True if Project Settings was opened, False otherwise.
        """
        success = self.navigate_menu("Edit", "Project Settings...")
        if success:
            time.sleep(self.WINDOW_OPEN_DELAY)
            # Invalidate cache since we changed window state
            self._cached_state = None
        return success

    def navigate_to_setting(
        self,
        category: str,
        subcategory: Optional[str] = None
    ) -> bool:
        """
        Navigate to a specific setting category in Project Settings.

        The Project Settings window must be open before calling this method.

        Args:
            category: The category name (e.g., "Player", "XR Plug-in Management")
            subcategory: Optional subcategory for nested settings

        Returns:
            True if navigation succeeded, False otherwise.

        Example:
            # Navigate to Player settings
            agent.navigate_to_setting("Player")

            # Navigate to XR Plug-in Management
            agent.navigate_to_setting("XR Plug-in Management")
        """
        # Ensure Project Settings is open
        if not self.is_window_visible(UnityWindow.PROJECT_SETTINGS):
            if not self.open_project_settings():
                return False
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Use keyboard search to find the category (Cmd+F in Project Settings)
        # Alternatively, click on the category in the left sidebar
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    -- Search for the category in the sidebar
                    -- Project Settings has a search field at the top
                    keystroke "l" using command down
                    delay 0.2
                    keystroke "a" using command down
                    delay 0.1
                    keystroke "{category}"
                    delay 0.5
                    -- Press down arrow and enter to select
                    key code 125
                    delay 0.2
                    key code 36
                    return "success"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)

        # If search doesn't work, try clicking directly
        if not success or output != "success":
            return self._click_settings_category(category)

        if subcategory:
            time.sleep(0.3)
            return self._click_settings_subcategory(subcategory)

        return True

    def set_checkbox(
        self,
        setting_path: str,
        value: bool,
        platform: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Toggle a checkbox setting in Project Settings.

        Args:
            setting_path: Path to the setting (e.g., "XR Plug-in Management/Android/Oculus")
            value: True to enable, False to disable
            platform: Optional platform context (e.g., "Android", "iOS")

        Returns:
            Tuple of (success, message).

        Example:
            # Enable Oculus XR plugin for Android
            agent.set_checkbox("Oculus", True, platform="Android")
        """
        # Parse the setting path
        parts = setting_path.split("/")
        category = parts[0] if parts else setting_path
        setting_name = parts[-1] if parts else setting_path

        # If platform specified, we may need to switch tabs
        if platform:
            if not self._select_platform_tab(platform):
                return (False, f"Failed to select platform: {platform}")
            time.sleep(0.3)

        # Navigate to the category if needed
        if len(parts) > 1 and not self.navigate_to_setting(category):
            return (False, f"Failed to navigate to category: {category}")

        # Now click the checkbox
        current_value = self._get_checkbox_state(setting_name)
        if current_value is None:
            return (False, f"Could not find checkbox: {setting_name}")

        if current_value == value:
            return (True, f"Checkbox already {'enabled' if value else 'disabled'}")

        # Click to toggle the checkbox
        if self._click_checkbox(setting_name):
            return (True, f"{'Enabled' if value else 'Disabled'} {setting_name}")

        return (False, f"Failed to toggle checkbox: {setting_name}")

    def enable_xr_plugin(
        self,
        platform: str,
        plugin_name: str
    ) -> Tuple[bool, str]:
        """
        Enable an XR plugin for a specific platform.

        This navigates to XR Plug-in Management and enables the specified plugin.

        Args:
            platform: Target platform ("Android", "iOS", "Standalone")
            plugin_name: Name of the XR plugin (e.g., "Oculus", "OpenXR")

        Returns:
            Tuple of (success, message).

        Example:
            # Enable Oculus for Android (Quest)
            agent.enable_xr_plugin("Android", "Oculus")

            # Enable OpenXR for Standalone
            agent.enable_xr_plugin("Standalone", "OpenXR")
        """
        # First check if XR Plug-in Management is installed
        xr_installed = self._is_xr_management_installed()
        if not xr_installed:
            # Try to install XR Plug-in Management
            install_success, install_msg = self._install_xr_management()
            if not install_success:
                return (False, f"XR Plug-in Management not installed: {install_msg}")
            time.sleep(2.0)  # Wait for installation

        # Open Project Settings and navigate to XR Plug-in Management
        if not self.navigate_to_setting("XR Plug-in Management"):
            return (False, "Failed to navigate to XR Plug-in Management")
        time.sleep(0.5)

        # Select the platform tab
        if not self._select_platform_tab(platform):
            return (False, f"Failed to select platform tab: {platform}")
        time.sleep(0.3)

        # Check current state and enable if needed
        plugins = self._get_xr_plugins_for_platform(platform)
        if plugin_name in plugins:
            return (True, f"{plugin_name} already enabled for {platform}")

        # Enable the plugin by clicking its checkbox
        if self._click_xr_plugin_checkbox(plugin_name, True):
            time.sleep(0.5)
            # Verify it was enabled
            plugins_after = self._get_xr_plugins_for_platform(platform)
            if plugin_name in plugins_after:
                return (True, f"Enabled {plugin_name} for {platform}")
            return (False, f"Clicked checkbox but {plugin_name} not enabled")

        return (False, f"Could not find XR plugin checkbox: {plugin_name}")

    def get_xr_plugins(self, platform: Optional[str] = None) -> List[str]:
        """
        Get list of enabled XR plugins.

        Args:
            platform: Optional platform to check. If None, returns all platforms.

        Returns:
            List of enabled XR plugin names.

        Example:
            # Get all Android XR plugins
            plugins = agent.get_xr_plugins("Android")
            # Returns e.g., ["Oculus"]
        """
        if platform:
            return self._get_xr_plugins_for_platform(platform)

        # Get plugins for all platforms
        all_plugins = []
        for plat in ["Standalone", "Android", "iOS"]:
            plugins = self._get_xr_plugins_for_platform(plat)
            for plugin in plugins:
                if plugin not in all_plugins:
                    all_plugins.append(plugin)
        return all_plugins

    # =========================================================================
    # Project Settings Internal Helpers
    # =========================================================================

    def _click_settings_category(self, category: str) -> bool:
        """
        Click on a category in the Project Settings sidebar.

        Args:
            category: Name of the category to click.

        Returns:
            True if successful, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    -- Look for the category in outline/tree views
                    set categoryRow to row 1 of outline 1 of scroll area 1 of psWindow whose value of static text 1 contains "{category}"
                    click categoryRow
                    return "success"
                on error
                    -- Try alternative: click static text directly
                    try
                        click static text "{category}" of scroll area 1 of psWindow
                        return "success"
                    on error errMsg
                        return "error: " & errMsg
                    end try
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _click_settings_subcategory(self, subcategory: str) -> bool:
        """Click on a subcategory in Project Settings."""
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    click static text "{subcategory}" of psWindow
                    return "success"
                on error
                    return "failed"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _select_platform_tab(self, platform: str) -> bool:
        """
        Select a platform tab in Project Settings.

        Args:
            platform: Platform name ("Android", "iOS", "Standalone")

        Returns:
            True if tab was selected, False otherwise.
        """
        # Platform tabs are usually represented by icons with tooltips
        # We need to click the correct tab button
        platform_icons = {
            "Standalone": 1,  # Desktop icon is usually first
            "Android": 2,     # Android robot icon
            "iOS": 3,         # Apple icon
            "WebGL": 4,       # Web icon
        }

        tab_index = platform_icons.get(platform, 0)
        if tab_index == 0:
            return False

        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    -- Platform tabs are in a tab group or radio buttons
                    -- Try clicking the Nth tab/button in the platform selector
                    try
                        click tab group 1's radio button {tab_index} of psWindow
                        return "success"
                    on error
                        -- Try button approach
                        click button {tab_index} of group 1 of psWindow
                        return "success"
                    end try
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if success and output == "success":
            return True

        # Alternative: Try clicking by platform name in UI
        return self._click_platform_by_name(platform)

    def _click_platform_by_name(self, platform: str) -> bool:
        """Click platform tab by searching for platform name."""
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Search for clickable elements containing the platform name
                    set psWindow to window "Project Settings"
                    set allElements to entire contents of psWindow
                    repeat with elem in allElements
                        try
                            if description of elem contains "{platform}" then
                                click elem
                                return "success"
                            end if
                        end try
                    end repeat
                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _get_checkbox_state(self, checkbox_name: str) -> Optional[bool]:
        """
        Get the current state of a checkbox.

        Args:
            checkbox_name: Name of the checkbox.

        Returns:
            True if checked, False if unchecked, None if not found.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    set cb to checkbox "{checkbox_name}" of psWindow
                    if value of cb is 1 then
                        return "checked"
                    else
                        return "unchecked"
                    end if
                on error
                    -- Try searching in scroll areas
                    try
                        set cb to checkbox 1 of scroll area 2 of psWindow whose description contains "{checkbox_name}"
                        if value of cb is 1 then
                            return "checked"
                        else
                            return "unchecked"
                        end if
                    on error
                        return "not_found"
                    end try
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success:
            return None
        if output == "checked":
            return True
        if output == "unchecked":
            return False
        return None

    def _click_checkbox(self, checkbox_name: str) -> bool:
        """
        Click a checkbox to toggle its state.

        Args:
            checkbox_name: Name of the checkbox.

        Returns:
            True if clicked, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    click checkbox "{checkbox_name}" of psWindow
                    return "success"
                on error
                    -- Try searching in scroll areas
                    try
                        click checkbox 1 of scroll area 2 of psWindow whose description contains "{checkbox_name}"
                        return "success"
                    on error
                        return "failed"
                    end try
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _is_xr_management_installed(self) -> bool:
        """
        Check if XR Plug-in Management is installed.

        Returns:
            True if installed, False otherwise.
        """
        # Check if XR Plug-in Management appears in Project Settings
        project = self.get_open_project()
        if not project or not project.path:
            return False

        # Check for XR Management package in manifest
        manifest_path = f"{project.path}/Packages/manifest.json"
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                dependencies = manifest.get("dependencies", {})
                return "com.unity.xr.management" in dependencies
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            pass

        return False

    def _install_xr_management(self) -> Tuple[bool, str]:
        """
        Install XR Plug-in Management package.

        Returns:
            Tuple of (success, message).
        """
        # Open Package Manager and search for XR Plug-in Management
        if not self.open_package_manager():
            return (False, "Failed to open Package Manager")
        time.sleep(1.0)

        # Search for XR Plug-in Management
        if not self.search_package("XR Plugin Management"):
            return (False, "Failed to search for XR Plugin Management")
        time.sleep(1.0)

        # Click Install
        if self._click_package_button("Install"):
            # Wait for installation
            success, msg = self.wait_for_package_import(timeout=60.0)
            return (success, msg)

        return (False, "Could not find Install button")

    def _get_xr_plugins_for_platform(self, platform: str) -> List[str]:
        """
        Get list of enabled XR plugins for a specific platform.

        Args:
            platform: Platform to check ("Android", "iOS", "Standalone")

        Returns:
            List of enabled plugin names.
        """
        # Check XR settings in ProjectSettings folder
        project = self.get_open_project()
        if not project or not project.path:
            return []

        # Map platform names to build target group names used in settings files
        platform_mapping = {
            "Standalone": "Standalone",
            "Android": "Android",
            "iOS": "iPhone",  # Unity uses "iPhone" internally for iOS
        }
        target_platform = platform_mapping.get(platform, platform)

        # XR Plug-in Management stores settings in XR/Settings.asset files
        # or in XRGeneralSettingsPerBuildTarget.asset
        plugins: List[str] = []

        # Try XRGeneralSettingsPerBuildTarget.asset
        settings_path = f"{project.path}/ProjectSettings/XRGeneralSettingsPerBuildTarget.asset"
        try:
            with open(settings_path, 'r') as f:
                content = f.read()

                # Check if this platform section has loaders enabled
                # The file uses YAML-like format with platform-specific sections
                in_platform_section = False
                for line in content.split('\n'):
                    # Look for platform section markers
                    if target_platform in line:
                        in_platform_section = True
                    elif in_platform_section:
                        if line.strip().startswith('-') or 'm_' in line:
                            # Still in the same section
                            if "OculusLoader" in line:
                                plugins.append("Oculus")
                            if "OpenXRLoader" in line:
                                plugins.append("OpenXR")
                            if "ARCoreLoader" in line:
                                plugins.append("ARCore")
                            if "ARKitLoader" in line:
                                plugins.append("ARKit")
                        elif line.strip() and not line.strip().startswith('#'):
                            # New top-level section, stop scanning
                            in_platform_section = False
        except (FileNotFoundError, PermissionError):
            pass

        # If nothing found, try legacy XRSettings.asset
        if not plugins:
            legacy_path = f"{project.path}/ProjectSettings/XRSettings.asset"
            try:
                with open(legacy_path, 'r') as f:
                    content = f.read()
                    if "OculusLoader" in content or "Oculus" in content:
                        plugins.append("Oculus")
                    if "OpenXRLoader" in content or "OpenXR" in content:
                        plugins.append("OpenXR")
                    if "ARCoreLoader" in content:
                        plugins.append("ARCore")
                    if "ARKitLoader" in content:
                        plugins.append("ARKit")
            except (FileNotFoundError, PermissionError):
                pass

        return plugins

    def _click_xr_plugin_checkbox(self, plugin_name: str, enable: bool) -> bool:
        """
        Click an XR plugin checkbox in Project Settings.

        Args:
            plugin_name: Name of the XR plugin (e.g., "Oculus")
            enable: True to enable, False to disable

        Returns:
            True if checkbox was clicked, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    -- XR plugins are shown as checkboxes in the XR Plug-in Management pane
                    -- Look for checkbox with the plugin name
                    set allCheckboxes to checkboxes of scroll area 2 of psWindow
                    repeat with cb in allCheckboxes
                        try
                            if description of cb contains "{plugin_name}" or name of cb contains "{plugin_name}" then
                                set currentValue to value of cb
                                if ({enable} and currentValue is 0) or (not {enable} and currentValue is 1) then
                                    click cb
                                end if
                                return "success"
                            end if
                        end try
                    end repeat
                    -- Also try looking for the checkbox by label
                    try
                        click checkbox "{plugin_name}" of psWindow
                        return "success"
                    end try
                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    # =========================================================================
    # Meta XR Setup Tool Automation
    # =========================================================================

    def open_meta_setup_tool(self) -> Tuple[bool, str]:
        """
        Open the Meta XR Project Setup Tool.

        Navigates to Meta > Tools > Project Setup Tool. If the Meta menu
        doesn't exist, it indicates the Meta XR SDK is not installed.

        Returns:
            Tuple of (success, message).

        Example:
            success, msg = agent.open_meta_setup_tool()
            if not success:
                print(f"Failed: {msg}")
        """
        # First check if the Meta menu exists
        if not self._is_meta_menu_available():
            return (False, "Meta menu not found. Meta XR SDK may not be installed.")

        # Navigate to Meta > Tools > Project Setup Tool
        success = self.navigate_menu("Meta", "Tools", "Project Setup Tool")
        if success:
            time.sleep(self.WINDOW_OPEN_DELAY)
            # Invalidate cache since we changed window state
            self._cached_state = None
            return (True, "Project Setup Tool opened")

        return (False, "Failed to open Project Setup Tool via menu")

    def run_fix_all(self) -> MetaSetupResult:
        """
        Click the Fix All button in the Meta XR Project Setup Tool.

        The Project Setup Tool must be open before calling this method.
        This fixes all issues that can be automatically resolved.

        Returns:
            MetaSetupResult with fixed and remaining issues.

        Example:
            result = agent.run_fix_all()
            if result.success:
                print(f"Fixed {len(result.fixed_issues)} issues")
        """
        # Ensure the Setup Tool is open
        if not self.is_window_visible(UnityWindow.META_PROJECT_SETUP):
            open_success, msg = self.open_meta_setup_tool()
            if not open_success:
                return MetaSetupResult(
                    success=False,
                    fixed_issues=[],
                    remaining_issues=[],
                    message=msg,
                    meta_sdk_installed=False
                )
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Get issues before clicking Fix All
        issues_before = self.get_setup_issues()

        # Click Fix All button
        clicked = self._click_setup_tool_button("Fix All")
        if not clicked:
            return MetaSetupResult(
                success=False,
                fixed_issues=[],
                remaining_issues=issues_before,
                message="Fix All button not found or could not be clicked"
            )

        # Wait for fixes to be applied
        time.sleep(1.0)
        wait_success, wait_msg = self.wait_for_setup_complete(timeout=30.0)

        # Get issues after fixing
        issues_after = self.get_setup_issues()

        # Determine which issues were fixed
        fixed_titles = {issue.title for issue in issues_before} - {issue.title for issue in issues_after}
        fixed_issues = [
            MetaSetupIssue(
                title=title,
                status=MetaSetupIssueStatus.FIXED
            )
            for title in fixed_titles
        ]

        return MetaSetupResult(
            success=wait_success,
            fixed_issues=fixed_issues,
            remaining_issues=issues_after,
            message=f"Fixed {len(fixed_issues)} issues. {wait_msg}"
        )

    def run_apply_all(self) -> MetaSetupResult:
        """
        Click the Apply All button in the Meta XR Project Setup Tool.

        The Project Setup Tool must be open before calling this method.
        This applies all recommended settings (different from Fix All which
        only fixes required issues).

        Returns:
            MetaSetupResult with applied and remaining issues.

        Example:
            result = agent.run_apply_all()
            print(f"Applied settings: {result.message}")
        """
        # Ensure the Setup Tool is open
        if not self.is_window_visible(UnityWindow.META_PROJECT_SETUP):
            open_success, msg = self.open_meta_setup_tool()
            if not open_success:
                return MetaSetupResult(
                    success=False,
                    fixed_issues=[],
                    remaining_issues=[],
                    message=msg,
                    meta_sdk_installed=False
                )
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Get issues before clicking Apply All
        issues_before = self.get_setup_issues()

        # Click Apply All button
        clicked = self._click_setup_tool_button("Apply All")
        if not clicked:
            # Try alternative button names
            clicked = self._click_setup_tool_button("Apply Recommended")
            if not clicked:
                return MetaSetupResult(
                    success=False,
                    fixed_issues=[],
                    remaining_issues=issues_before,
                    message="Apply All button not found or could not be clicked"
                )

        # Wait for settings to be applied
        time.sleep(1.0)
        wait_success, wait_msg = self.wait_for_setup_complete(timeout=30.0)

        # Get issues after applying
        issues_after = self.get_setup_issues()

        # Determine which issues were resolved
        fixed_titles = {issue.title for issue in issues_before} - {issue.title for issue in issues_after}
        fixed_issues = [
            MetaSetupIssue(
                title=title,
                status=MetaSetupIssueStatus.FIXED
            )
            for title in fixed_titles
        ]

        return MetaSetupResult(
            success=wait_success,
            fixed_issues=fixed_issues,
            remaining_issues=issues_after,
            message=f"Applied {len(fixed_issues)} settings. {wait_msg}"
        )

    def get_setup_issues(self) -> List[MetaSetupIssue]:
        """
        Read current issues from the Meta XR Project Setup Tool.

        The Project Setup Tool should be open before calling this method.
        If not open, this will attempt to open it first.

        Returns:
            List of MetaSetupIssue objects representing current issues.

        Example:
            issues = agent.get_setup_issues()
            for issue in issues:
                print(f"{issue.level.value}: {issue.title}")
        """
        # Try to open the setup tool if not visible
        if not self.is_window_visible(UnityWindow.META_PROJECT_SETUP):
            open_success, _ = self.open_meta_setup_tool()
            if not open_success:
                return []
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Read issues from the setup tool window
        # The tool displays issues in a list with checkboxes/icons
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set setupWindow to window "Project Setup Tool"
                    set issueList to {}

                    -- Try to get text content from the window
                    -- Issues are typically shown in a scroll area with text elements
                    set allText to ""
                    try
                        set allElements to entire contents of setupWindow
                        repeat with elem in allElements
                            try
                                set elemText to value of elem as text
                                if elemText is not "" then
                                    set allText to allText & elemText & "|"
                                end if
                            end try
                            try
                                set elemText to description of elem as text
                                if elemText is not "" then
                                    set allText to allText & elemText & "|"
                                end if
                            end try
                        end repeat
                    end try

                    return allText
                on error errMsg
                    return "error:" & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success or output.startswith("error:"):
            return []

        # Parse the output to extract issues
        issues: List[MetaSetupIssue] = []
        if output:
            # Split by delimiter and look for issue patterns
            parts = output.split("|")
            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Look for common issue keywords in Meta XR Setup Tool
                issue_keywords = [
                    "Color Space",
                    "Graphics API",
                    "OpenXR",
                    "Oculus",
                    "Android",
                    "Manifest",
                    "Target API",
                    "Minimum API",
                    "ARM64",
                    "IL2CPP",
                    "Scripting Backend",
                    "XR Plugin",
                    "Input System",
                    "Activity",
                    "Internet Access"
                ]

                for keyword in issue_keywords:
                    if keyword.lower() in part.lower():
                        # This looks like an issue
                        level = MetaSetupIssueLevel.RECOMMENDED
                        if "required" in part.lower():
                            level = MetaSetupIssueLevel.REQUIRED
                        elif "optional" in part.lower():
                            level = MetaSetupIssueLevel.OPTIONAL

                        issue = MetaSetupIssue(
                            title=part[:100],  # Limit title length
                            level=level,
                            status=MetaSetupIssueStatus.UNFIXED,
                            description=part
                        )
                        # Avoid duplicates
                        if not any(i.title == issue.title for i in issues):
                            issues.append(issue)
                        break

        return issues

    def wait_for_setup_complete(self, timeout: float = 30.0) -> Tuple[bool, str]:
        """
        Wait for Meta XR Project Setup Tool operations to complete.

        Waits until no more progress indicators or until the tool
        shows completion status.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            Tuple of (success, message).

        Example:
            success, msg = agent.wait_for_setup_complete(timeout=60.0)
            if success:
                print("Setup operations completed")
        """
        start_time = time.time()
        poll_interval = 0.5

        while time.time() - start_time < timeout:
            # Check if Unity is busy (compiling, importing)
            is_importing = self._is_importing()
            is_compiling = self._is_compiling()

            if not is_importing and not is_compiling:
                # Also check if the setup tool is showing progress
                if not self._is_setup_tool_busy():
                    # Double-check after short delay
                    time.sleep(0.5)
                    if not self._is_setup_tool_busy():
                        return (True, "Setup operations completed")

            time.sleep(poll_interval)

        return (False, f"Timeout after {timeout} seconds waiting for setup to complete")

    def is_meta_sdk_installed(self) -> bool:
        """
        Check if Meta XR SDK is installed in the current project.

        Returns:
            True if Meta XR SDK is installed, False otherwise.

        Example:
            if agent.is_meta_sdk_installed():
                agent.open_meta_setup_tool()
        """
        return self._is_meta_menu_available()

    # =========================================================================
    # Meta XR Setup Tool Internal Helpers
    # =========================================================================

    def _is_meta_menu_available(self) -> bool:
        """
        Check if the Meta menu exists in Unity's menu bar.

        The Meta menu is added by the Meta XR SDK when installed.

        Returns:
            True if Meta menu exists, False otherwise.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    if exists menu bar item "Meta" of menu bar 1 then
                        return "yes"
                    end if
                    return "no"
                on error
                    return "no"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _click_setup_tool_button(self, button_name: str) -> bool:
        """
        Click a button in the Meta XR Project Setup Tool window.

        Args:
            button_name: Name of the button (e.g., "Fix All", "Apply All")

        Returns:
            True if button was clicked, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set setupWindow to window "Project Setup Tool"

                    -- Try clicking button by name directly
                    try
                        click button "{button_name}" of setupWindow
                        return "success"
                    end try

                    -- Try looking in scroll areas
                    try
                        repeat with scrollArea in scroll areas of setupWindow
                            try
                                click button "{button_name}" of scrollArea
                                return "success"
                            end try
                        end repeat
                    end try

                    -- Try looking in groups
                    try
                        repeat with grp in groups of setupWindow
                            try
                                click button "{button_name}" of grp
                                return "success"
                            end try
                        end repeat
                    end try

                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _is_setup_tool_busy(self) -> bool:
        """
        Check if the Meta XR Project Setup Tool is showing progress.

        Returns:
            True if the tool appears to be processing, False otherwise.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set setupWindow to window "Project Setup Tool"

                    -- Check for progress indicators
                    if exists progress indicator 1 of setupWindow then
                        return "yes"
                    end if

                    -- Check window name for progress indication
                    set windowName to name of setupWindow
                    if windowName contains "..." or windowName contains "Progress" then
                        return "yes"
                    end if

                    return "no"
                on error
                    return "no"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _get_setup_tool_status(self) -> Tuple[int, int]:
        """
        Get the number of issues and fixed items from the setup tool.

        Returns:
            Tuple of (total_issues, fixed_issues).
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set setupWindow to window "Project Setup Tool"

                    -- Try to get counts from static text elements
                    set allText to ""
                    repeat with st in static texts of setupWindow
                        try
                            set allText to allText & value of st & " "
                        end try
                    end repeat

                    return allText
                on error errMsg
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success:
            return (0, 0)

        # Parse output to find issue counts
        # Common patterns: "3 issues", "2 remaining", "5 fixed"
        import re as regex
        total = 0
        fixed = 0

        total_match = regex.search(r'(\d+)\s*(?:issues?|items?)', output.lower())
        if total_match:
            total = int(total_match.group(1))

        fixed_match = regex.search(r'(\d+)\s*fixed', output.lower())
        if fixed_match:
            fixed = int(fixed_match.group(1))

        return (total, fixed)

    # =========================================================================
    # Scripting Define Symbols Automation
    # =========================================================================

    def get_define_symbols(self, platform: Optional[str] = None) -> List[str]:
        """
        Get the current scripting define symbols for a platform.

        Reads symbols from ProjectSettings/ProjectSettings.asset file.

        Args:
            platform: Platform to get symbols for ("Android", "iOS", "Standalone").
                     If None, returns symbols for the current active platform.

        Returns:
            List of define symbol strings.

        Example:
            symbols = agent.get_define_symbols("Android")
            # Returns e.g., ["OCULUS_XR_SDK", "UNITY_POST_PROCESSING"]
        """
        project = self.get_open_project()
        if not project or not project.path:
            return []

        # Determine platform build target group
        if platform is None:
            platform = self._get_active_platform_name()

        build_target_group = self._platform_to_build_target_group(platform)

        # Read from ProjectSettings.asset
        settings_path = f"{project.path}/ProjectSettings/ProjectSettings.asset"
        try:
            with open(settings_path, 'r') as f:
                content = f.read()
        except (FileNotFoundError, PermissionError):
            return []

        # Parse scriptingDefineSymbols section
        # Format in YAML: scriptingDefineSymbols: { buildTargetGroup: symbols }
        symbols = self._parse_define_symbols_for_platform(content, build_target_group)
        return symbols

    def add_define_symbol(
        self,
        platform: str,
        symbol: str
    ) -> Tuple[bool, List[str]]:
        """
        Add a scripting define symbol for a platform.

        Navigates to Player Settings and adds the symbol to the Scripting Define Symbols
        field. Triggers recompilation automatically.

        Args:
            platform: Target platform ("Android", "iOS", "Standalone")
            symbol: Symbol to add (e.g., "OCULUS_XR_SDK")

        Returns:
            Tuple of (success, current_symbols_after_change).

        Example:
            success, symbols = agent.add_define_symbol("Android", "OCULUS_XR_SDK")
            if success:
                print(f"Added symbol. Current symbols: {symbols}")
        """
        # Get current symbols
        current_symbols = self.get_define_symbols(platform)

        # Check if already exists
        if symbol in current_symbols:
            return (True, current_symbols)

        # Add via UI
        success = self._modify_define_symbols_via_ui(
            platform=platform,
            add_symbol=symbol,
            remove_symbol=None
        )

        if success:
            # Wait for recompilation
            self.wait_for_recompilation()
            # Return updated symbols
            updated_symbols = self.get_define_symbols(platform)
            return (True, updated_symbols)

        return (False, current_symbols)

    def remove_define_symbol(
        self,
        platform: str,
        symbol: str
    ) -> Tuple[bool, List[str]]:
        """
        Remove a scripting define symbol from a platform.

        Navigates to Player Settings and removes the symbol from the Scripting Define
        Symbols field. Triggers recompilation automatically.

        Args:
            platform: Target platform ("Android", "iOS", "Standalone")
            symbol: Symbol to remove

        Returns:
            Tuple of (success, current_symbols_after_change).

        Example:
            success, symbols = agent.remove_define_symbol("Android", "DEBUG_MODE")
            if success:
                print(f"Removed symbol. Current symbols: {symbols}")
        """
        # Get current symbols
        current_symbols = self.get_define_symbols(platform)

        # Check if exists
        if symbol not in current_symbols:
            return (True, current_symbols)  # Already removed

        # Remove via UI
        success = self._modify_define_symbols_via_ui(
            platform=platform,
            add_symbol=None,
            remove_symbol=symbol
        )

        if success:
            # Wait for recompilation
            self.wait_for_recompilation()
            # Return updated symbols
            updated_symbols = self.get_define_symbols(platform)
            return (True, updated_symbols)

        return (False, current_symbols)

    def wait_for_recompilation(self, timeout: float = 60.0) -> Tuple[bool, str]:
        """
        Wait for Unity to finish recompiling scripts.

        After modifying scripting define symbols, Unity needs to recompile
        all scripts. This method waits until compilation is complete.

        Args:
            timeout: Maximum time to wait in seconds (default 60s).

        Returns:
            Tuple of (success, message).

        Example:
            success, msg = agent.wait_for_recompilation()
            if success:
                print("Recompilation complete")
        """
        start_time = time.time()

        # Brief delay to let Unity detect the change
        time.sleep(0.5)

        # Poll until compilation is complete or timeout
        while time.time() - start_time < timeout:
            # Check if compiling
            if self._is_compiling():
                time.sleep(0.5)
                continue

            # Check if importing
            if self._is_importing():
                time.sleep(0.5)
                continue

            # Double-check after a brief pause (Unity may start new compilation)
            time.sleep(0.3)
            if not self._is_compiling() and not self._is_importing():
                elapsed = time.time() - start_time
                return (True, f"Recompilation complete in {elapsed:.1f}s")

        return (False, f"Timeout waiting for recompilation after {timeout}s")

    def set_define_symbols(
        self,
        platform: str,
        symbols: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Set all scripting define symbols for a platform (replacing existing).

        This is a convenience method that sets the exact list of symbols,
        removing any not in the provided list and adding any missing.

        Args:
            platform: Target platform ("Android", "iOS", "Standalone")
            symbols: Complete list of symbols to set

        Returns:
            Tuple of (success, final_symbols).

        Example:
            success, final = agent.set_define_symbols("Android", ["OCULUS_XR_SDK", "MY_FEATURE"])
        """
        # Navigate to Player Settings and set symbols directly
        success = self._set_all_define_symbols_via_ui(platform, symbols)

        if success:
            # Wait for recompilation
            self.wait_for_recompilation()
            final_symbols = self.get_define_symbols(platform)
            return (True, final_symbols)

        return (False, self.get_define_symbols(platform))

    # =========================================================================
    # Scripting Define Symbols Internal Helpers
    # =========================================================================

    def _platform_to_build_target_group(self, platform: str) -> int:
        """
        Convert platform name to Unity's BuildTargetGroup integer.

        Args:
            platform: Platform name ("Android", "iOS", "Standalone")

        Returns:
            BuildTargetGroup integer value.
        """
        # Unity BuildTargetGroup enum values
        platform_map = {
            "Standalone": 1,
            "iOS": 4,
            "Android": 7,
            "WebGL": 13,
            "PS4": 19,
            "XboxOne": 21,
            "tvOS": 25,
            "Switch": 38,
            "PS5": 44,
        }
        return platform_map.get(platform, 1)  # Default to Standalone

    def _get_active_platform_name(self) -> str:
        """
        Get the name of the currently active build platform.

        Returns:
            Platform name string.
        """
        current = self.get_current_platform()
        if current:
            # Map build target to platform name
            target_to_name = {
                "Android": "Android",
                "iOS": "iOS",
                "Win": "Standalone",
                "Win64": "Standalone",
                "OSXUniversal": "Standalone",
                "Linux64": "Standalone",
                "WebGL": "WebGL",
            }
            return target_to_name.get(current, "Standalone")
        return "Standalone"

    def _parse_define_symbols_for_platform(
        self,
        content: str,
        build_target_group: int
    ) -> List[str]:
        """
        Parse scripting define symbols from ProjectSettings.asset content.

        Args:
            content: Contents of ProjectSettings.asset file
            build_target_group: BuildTargetGroup integer value

        Returns:
            List of symbol strings.
        """
        # Look for scriptingDefineSymbols section
        # Format varies between Unity versions, common formats:
        # scriptingDefineSymbols:
        #   7: SYMBOL1;SYMBOL2
        # or
        # scriptingDefineSymbols: {7: SYMBOL1;SYMBOL2}

        symbols = []

        # Try to find the platform-specific symbols
        import re as regex

        # Pattern 1: YAML block style
        pattern1 = rf'scriptingDefineSymbols:\s*\n\s*{build_target_group}:\s*([^\n]*)'
        match1 = regex.search(pattern1, content)
        if match1:
            symbols_str = match1.group(1).strip()
            if symbols_str:
                symbols = [s.strip() for s in symbols_str.split(';') if s.strip()]
                return symbols

        # Pattern 2: Inline style
        pattern2 = rf'scriptingDefineSymbols:\s*\{{\s*{build_target_group}:\s*([^}}\n]*)'
        match2 = regex.search(pattern2, content)
        if match2:
            symbols_str = match2.group(1).strip()
            # Handle potential trailing comma and other platform entries
            if ',' in symbols_str:
                symbols_str = symbols_str.split(',')[0].strip()
            if symbols_str:
                symbols = [s.strip() for s in symbols_str.split(';') if s.strip()]
                return symbols

        # Pattern 3: Multi-line with indentation
        # scriptingDefineSymbols:
        #   1: SYMBOL1;SYMBOL2
        #   7: SYMBOL3;SYMBOL4
        pattern3 = rf'scriptingDefineSymbols:.*?{build_target_group}:\s*([^\n]*?)(?=\n\s*\d+:|$)'
        match3 = regex.search(pattern3, content, regex.DOTALL)
        if match3:
            symbols_str = match3.group(1).strip()
            if symbols_str:
                symbols = [s.strip() for s in symbols_str.split(';') if s.strip()]
                return symbols

        return symbols

    def _modify_define_symbols_via_ui(
        self,
        platform: str,
        add_symbol: Optional[str],
        remove_symbol: Optional[str]
    ) -> bool:
        """
        Modify scripting define symbols via the Unity UI.

        Opens Project Settings > Player and modifies the Scripting Define Symbols
        text field.

        Args:
            platform: Target platform
            add_symbol: Symbol to add (or None)
            remove_symbol: Symbol to remove (or None)

        Returns:
            True if modification succeeded, False otherwise.
        """
        # Open Project Settings if not visible
        if not self.is_window_visible(UnityWindow.PROJECT_SETTINGS):
            if not self.open_project_settings():
                return False
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Navigate to Player settings
        if not self.navigate_to_setting("Player"):
            return False
        time.sleep(0.5)

        # Select platform tab
        if not self._select_platform_tab(platform):
            return False
        time.sleep(0.3)

        # Get current symbols
        current_symbols = self.get_define_symbols(platform)

        # Calculate new symbols
        new_symbols = current_symbols.copy()
        if add_symbol and add_symbol not in new_symbols:
            new_symbols.append(add_symbol)
        if remove_symbol and remove_symbol in new_symbols:
            new_symbols.remove(remove_symbol)

        # Set the new symbols string
        new_symbols_str = ";".join(new_symbols)

        # Use keyboard navigation to find and modify the field
        success = self._set_define_symbols_text_field(new_symbols_str)

        return success

    def _set_all_define_symbols_via_ui(
        self,
        platform: str,
        symbols: List[str]
    ) -> bool:
        """
        Set all scripting define symbols via UI.

        Args:
            platform: Target platform
            symbols: Complete list of symbols to set

        Returns:
            True if successful, False otherwise.
        """
        # Open Project Settings if not visible
        if not self.is_window_visible(UnityWindow.PROJECT_SETTINGS):
            if not self.open_project_settings():
                return False
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Navigate to Player settings
        if not self.navigate_to_setting("Player"):
            return False
        time.sleep(0.5)

        # Select platform tab
        if not self._select_platform_tab(platform):
            return False
        time.sleep(0.3)

        # Set the symbols string
        symbols_str = ";".join(symbols)
        return self._set_define_symbols_text_field(symbols_str)

    def _set_define_symbols_text_field(self, symbols_str: str) -> bool:
        """
        Set the Scripting Define Symbols text field value.

        Searches for the text field in Player settings and sets its value.

        Args:
            symbols_str: Semicolon-separated symbols string

        Returns:
            True if successful, False otherwise.
        """
        # First, try to search for "Scripting Define" in the settings
        # Use Cmd+L to open search, then search for the setting
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"

                    -- Try to use search to find Scripting Define Symbols
                    keystroke "l" using command down
                    delay 0.3
                    keystroke "a" using command down
                    delay 0.1
                    keystroke "Scripting Define"
                    delay 0.5

                    -- Press down arrow to select result
                    key code 125
                    delay 0.2
                    key code 36
                    delay 0.5

                    -- Now try to find and select the text field
                    -- First, click on "Other Settings" or expand it
                    -- Then look for the Scripting Define Symbols field

                    return "navigated"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success or "error" in output.lower():
            # Fallback: try direct navigation
            pass

        # Now set the text field value
        # The field is typically a text field that we need to select all and type
        set_script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"

                    -- Search for text fields in the window that might be the define symbols
                    set allTextFields to text fields of psWindow
                    repeat with tf in allTextFields
                        try
                            -- Try to identify the Scripting Define Symbols field
                            -- It's usually near text containing "Scripting Define"
                            set tfValue to value of tf
                            -- Select all and replace
                            click tf
                            delay 0.1
                            keystroke "a" using command down
                            delay 0.1
                            keystroke "{symbols_str}"
                            delay 0.2
                            -- Press Enter to confirm
                            key code 36
                            return "success"
                        end try
                    end repeat

                    -- Alternative: Try to find in scroll areas
                    repeat with scrollArea in scroll areas of psWindow
                        try
                            set scrollTextFields to text fields of scrollArea
                            if (count of scrollTextFields) > 0 then
                                set tf to item 1 of scrollTextFields
                                click tf
                                delay 0.1
                                keystroke "a" using command down
                                delay 0.1
                                keystroke "{symbols_str}"
                                delay 0.2
                                key code 36
                                return "success"
                            end if
                        end try
                    end repeat

                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(set_script)

        if success and output == "success":
            return True

        # Final fallback: Try to click "Apply" button if visible to ensure changes are saved
        self._click_button("Apply", "Project Settings")

        return success and output == "success"

    def _navigate_to_player_other_settings(self, platform: str) -> bool:
        """
        Navigate to Player > Other Settings in Project Settings.

        The Scripting Define Symbols field is located in Player > Other Settings.

        Args:
            platform: Target platform

        Returns:
            True if navigation succeeded, False otherwise.
        """
        # Ensure Project Settings is open
        if not self.is_window_visible(UnityWindow.PROJECT_SETTINGS):
            if not self.open_project_settings():
                return False
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Navigate to Player
        if not self._click_settings_category("Player"):
            return False
        time.sleep(0.3)

        # Select platform tab
        if not self._select_platform_tab(platform):
            return False
        time.sleep(0.3)

        # Try to expand "Other Settings" section if collapsed
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    set psWindow to window "Project Settings"
                    -- Look for "Other Settings" disclosure triangle or header
                    try
                        click static text "Other Settings" of psWindow
                        return "clicked"
                    end try
                    -- Try finding in scroll area
                    try
                        click static text "Other Settings" of scroll area 2 of psWindow
                        return "clicked"
                    end try
                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        self._run_applescript(script)
        # Even if click fails, the section might already be expanded
        return True

    # =========================================================================
    # Unity Build Automation
    # =========================================================================

    def open_build_settings(self) -> bool:
        """
        Open the Unity Build Settings window.

        Uses File > Build Settings menu navigation or keyboard shortcut.

        Returns:
            True if Build Settings was opened, False otherwise.

        Example:
            agent.open_build_settings()
        """
        # Try keyboard shortcut first (Cmd+Shift+B)
        success = self.open_menu_with_shortcut("b", ["command", "shift"])
        if success:
            time.sleep(self.WINDOW_OPEN_DELAY)
            # Invalidate cache since we changed window state
            self._cached_state = None
            return True

        # Fallback to menu navigation
        success = self.navigate_menu("File", "Build Settings...")
        if success:
            time.sleep(self.WINDOW_OPEN_DELAY)
            self._cached_state = None
        return success

    def switch_platform(self, platform: str) -> Tuple[bool, str]:
        """
        Switch to a different build platform.

        Opens Build Settings if not already open and switches to the specified
        platform. Platform switching may take some time as Unity reimports assets.

        Args:
            platform: Target platform name (e.g., "Android", "iOS", "Standalone")

        Returns:
            Tuple of (success, message).

        Example:
            success, msg = agent.switch_platform("Android")
            if success:
                print("Switched to Android")
        """
        # Ensure Build Settings is open
        if not self.is_window_visible(UnityWindow.BUILD_SETTINGS):
            if not self.open_build_settings():
                return (False, "Failed to open Build Settings")
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Map user-friendly names to Unity's internal platform names
        platform_map = {
            "android": "Android",
            "ios": "iOS",
            "standalone": "PC, Mac & Linux Standalone",
            "windows": "PC, Mac & Linux Standalone",
            "macos": "PC, Mac & Linux Standalone",
            "mac": "PC, Mac & Linux Standalone",
            "linux": "PC, Mac & Linux Standalone",
            "webgl": "WebGL",
            "tvos": "tvOS",
        }

        target_platform = platform_map.get(platform.lower(), platform)

        # Click on the platform in the platform list
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set bsWindow to window "Build Settings"
                    -- Look for the platform in the list
                    set platformFound to false

                    -- Try clicking in outline/table view
                    try
                        set platformRow to row 1 of outline 1 of scroll area 1 of bsWindow whose value of static text 1 contains "{target_platform}"
                        click platformRow
                        set platformFound to true
                    end try

                    -- Try alternative: click static text with platform name
                    if not platformFound then
                        try
                            click static text "{target_platform}" of bsWindow
                            set platformFound to true
                        end try
                    end if

                    if platformFound then
                        return "selected"
                    else
                        return "not_found"
                    end if
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if not success or output == "not_found":
            return (False, f"Platform not found: {target_platform}")
        if output.startswith("error:"):
            return (False, output)

        time.sleep(0.3)

        # Click "Switch Platform" button
        clicked = self._click_build_settings_button("Switch Platform")
        if not clicked:
            # Platform might already be selected
            is_current = self._is_current_platform(target_platform)
            if is_current:
                return (True, f"Already on {target_platform} platform")
            return (False, "Switch Platform button not found")

        # Wait for platform switch to complete (can take a while)
        time.sleep(1.0)
        wait_success, wait_msg = self._wait_for_platform_switch(timeout=300.0)

        if wait_success:
            return (True, f"Switched to {target_platform}")
        return (False, f"Platform switch timeout: {wait_msg}")

    def set_build_options(self, options: BuildOptions) -> Tuple[bool, str]:
        """
        Configure build options in Build Settings.

        Args:
            options: BuildOptions object with desired settings.

        Returns:
            Tuple of (success, message).

        Example:
            options = BuildOptions(
                development_build=True,
                autoconnect_profiler=True
            )
            agent.set_build_options(options)
        """
        # Ensure Build Settings is open
        if not self.is_window_visible(UnityWindow.BUILD_SETTINGS):
            if not self.open_build_settings():
                return (False, "Failed to open Build Settings")
            time.sleep(self.WINDOW_OPEN_DELAY)

        errors = []

        # Set Development Build checkbox
        if options.development_build:
            if not self._set_build_checkbox("Development Build", True):
                errors.append("Failed to set Development Build")

        # Set Autoconnect Profiler (only visible when Development Build is on)
        if options.autoconnect_profiler:
            if not self._set_build_checkbox("Autoconnect Profiler", True):
                errors.append("Failed to set Autoconnect Profiler")

        # Set Deep Profiling Support
        if options.deep_profiling:
            if not self._set_build_checkbox("Deep Profiling Support", True):
                errors.append("Failed to set Deep Profiling Support")

        # Set Script Debugging
        if options.script_debugging:
            if not self._set_build_checkbox("Script Debugging", True):
                errors.append("Failed to set Script Debugging")

        # Set Build App Bundle (Android specific)
        if options.build_app_bundle:
            if not self._set_build_checkbox("Build App Bundle", True):
                errors.append("Failed to set Build App Bundle")

        # Set Export Project (Android specific)
        if options.export_project:
            if not self._set_build_checkbox("Export Project", True):
                errors.append("Failed to set Export Project")

        if errors:
            return (False, "; ".join(errors))

        return (True, "Build options configured successfully")

    def build(self, output_path: str, timeout: float = 600.0) -> BuildResultInfo:
        """
        Build the project and wait for completion.

        Args:
            output_path: Path for the build output (e.g., "builds/MyGame.apk")
            timeout: Maximum build time in seconds (default 10 minutes).

        Returns:
            BuildResultInfo with detailed build information.

        Example:
            result = agent.build("builds/MyGame.apk")
            if result.result == BuildResult.SUCCESS:
                print(f"Build completed: {result.output_path}")
            else:
                for error in result.errors:
                    print(f"Error: {error.message}")
        """
        start_time = time.time()

        # Ensure Build Settings is open
        if not self.is_window_visible(UnityWindow.BUILD_SETTINGS):
            if not self.open_build_settings():
                return BuildResultInfo(
                    result=BuildResult.FAILED,
                    message="Failed to open Build Settings"
                )
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Click Build button
        clicked = self._click_build_settings_button("Build")
        if not clicked:
            return BuildResultInfo(
                result=BuildResult.FAILED,
                message="Build button not found"
            )

        time.sleep(0.5)

        # Handle save dialog - enter the output path
        if not self._enter_build_output_path(output_path):
            return BuildResultInfo(
                result=BuildResult.FAILED,
                message="Failed to enter output path"
            )

        # Wait for build to complete
        build_success, build_msg, errors = self._wait_for_build_complete(timeout)

        build_time = time.time() - start_time

        if build_success:
            return BuildResultInfo(
                result=BuildResult.SUCCESS,
                output_path=output_path,
                build_time_seconds=build_time,
                message=build_msg
            )
        else:
            return BuildResultInfo(
                result=BuildResult.FAILED,
                build_time_seconds=build_time,
                errors=errors,
                message=build_msg
            )

    def build_and_run(self, device: Optional[str] = None, timeout: float = 600.0) -> BuildResultInfo:
        """
        Build the project and deploy to a connected device.

        Args:
            device: Optional device ID to deploy to. If None, uses first connected device.
            timeout: Maximum build time in seconds (default 10 minutes).

        Returns:
            BuildResultInfo with detailed build information.

        Example:
            result = agent.build_and_run()
            if result.result == BuildResult.SUCCESS:
                print("Build and Run completed!")
        """
        start_time = time.time()

        # Check for connected devices
        devices = self.get_connected_devices()
        if not devices:
            return BuildResultInfo(
                result=BuildResult.FAILED,
                message="No devices connected"
            )

        # If device specified, verify it's connected
        if device:
            device_found = any(d.device_id == device for d in devices)
            if not device_found:
                return BuildResultInfo(
                    result=BuildResult.FAILED,
                    message=f"Device not found: {device}"
                )

        # Ensure Build Settings is open
        if not self.is_window_visible(UnityWindow.BUILD_SETTINGS):
            if not self.open_build_settings():
                return BuildResultInfo(
                    result=BuildResult.FAILED,
                    message="Failed to open Build Settings"
                )
            time.sleep(self.WINDOW_OPEN_DELAY)

        # Click Build And Run button
        clicked = self._click_build_settings_button("Build And Run")
        if not clicked:
            return BuildResultInfo(
                result=BuildResult.FAILED,
                message="Build And Run button not found"
            )

        # Wait for build and deployment to complete
        build_success, build_msg, errors = self._wait_for_build_complete(timeout)

        build_time = time.time() - start_time

        if build_success:
            return BuildResultInfo(
                result=BuildResult.SUCCESS,
                build_time_seconds=build_time,
                message=build_msg
            )
        else:
            return BuildResultInfo(
                result=BuildResult.FAILED,
                build_time_seconds=build_time,
                errors=errors,
                message=build_msg
            )

    def get_connected_devices(self) -> List[ConnectedDevice]:
        """
        Get list of connected Android devices via ADB.

        Returns:
            List of ConnectedDevice objects.

        Example:
            devices = agent.get_connected_devices()
            for device in devices:
                print(f"{device.device_id}: {device.model}")
        """
        devices: List[ConnectedDevice] = []

        try:
            # Run adb devices
            result = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return devices

            # Parse output
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header line
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                device_id = parts[0]
                state = parts[1]

                # Extract model if available
                model = "Unknown"
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":")[1]
                        break
                    if part.startswith("device:"):
                        model = part.split(":")[1]
                        break

                # Check if it's a Quest device
                is_quest = any(q in model.lower() for q in ["quest", "hollywood", "monterey"])

                devices.append(ConnectedDevice(
                    device_id=device_id,
                    model=model,
                    state=state,
                    is_quest=is_quest
                ))

        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return devices

    def get_current_platform(self) -> Optional[str]:
        """
        Get the currently selected build platform.

        Returns:
            Platform name if detected, None otherwise.
        """
        # Check EditorUserBuildSettings in the project
        project = self.get_open_project()
        if not project or not project.path:
            return None

        # Read EditorUserBuildSettings.asset
        settings_path = f"{project.path}/ProjectSettings/EditorBuildSettings.asset"
        try:
            with open(settings_path, 'r') as f:
                content = f.read()
                # Look for activeBuildTarget
                if "Android" in content:
                    return "Android"
                if "iOS" in content or "iPhone" in content:
                    return "iOS"
                if "WebGL" in content:
                    return "WebGL"
                if "StandaloneOSX" in content or "StandaloneWindows" in content:
                    return "Standalone"
        except (FileNotFoundError, PermissionError):
            pass

        return None

    # =========================================================================
    # Build Automation Internal Helpers
    # =========================================================================

    def _click_build_settings_button(self, button_name: str) -> bool:
        """
        Click a button in the Build Settings window.

        Args:
            button_name: Name of the button (e.g., "Build", "Build And Run", "Switch Platform")

        Returns:
            True if button was clicked, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set bsWindow to window "Build Settings"

                    -- Try clicking button directly
                    try
                        click button "{button_name}" of bsWindow
                        return "success"
                    end try

                    -- Try looking in groups
                    try
                        repeat with grp in groups of bsWindow
                            try
                                click button "{button_name}" of grp
                                return "success"
                            end try
                        end repeat
                    end try

                    -- Try looking in scroll areas
                    try
                        repeat with scrollArea in scroll areas of bsWindow
                            try
                                click button "{button_name}" of scrollArea
                                return "success"
                            end try
                        end repeat
                    end try

                    return "not_found"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _set_build_checkbox(self, checkbox_name: str, value: bool) -> bool:
        """
        Set a checkbox in Build Settings.

        Args:
            checkbox_name: Name of the checkbox.
            value: True to check, False to uncheck.

        Returns:
            True if successful, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    set bsWindow to window "Build Settings"

                    -- Find the checkbox
                    set cb to checkbox "{checkbox_name}" of bsWindow

                    -- Get current value
                    set currentValue to value of cb

                    -- Toggle if needed
                    if {value} then
                        if currentValue is 0 then
                            click cb
                        end if
                    else
                        if currentValue is 1 then
                            click cb
                        end if
                    end if

                    return "success"
                on error
                    -- Try finding in scroll areas
                    try
                        repeat with scrollArea in scroll areas of bsWindow
                            try
                                set cb to checkbox "{checkbox_name}" of scrollArea
                                set currentValue to value of cb
                                if {value} then
                                    if currentValue is 0 then
                                        click cb
                                    end if
                                else
                                    if currentValue is 1 then
                                        click cb
                                    end if
                                end if
                                return "success"
                            end try
                        end repeat
                    end try
                    return "not_found"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _is_current_platform(self, platform: str) -> bool:
        """
        Check if the specified platform is the current build target.

        Args:
            platform: Platform name to check.

        Returns:
            True if current platform matches, False otherwise.
        """
        current = self.get_current_platform()
        if not current:
            return False

        # Normalize platform names for comparison
        platform_lower = platform.lower()
        current_lower = current.lower()

        if platform_lower == current_lower:
            return True

        # Handle aliases
        if platform_lower in ["pc, mac & linux standalone", "standalone", "windows", "macos", "linux"]:
            if current_lower in ["standalone", "windows", "macos", "linux"]:
                return True

        return False

    def _wait_for_platform_switch(self, timeout: float = 300.0) -> Tuple[bool, str]:
        """
        Wait for platform switch to complete.

        Platform switching involves reimporting assets which can take a long time.

        Args:
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (success, message).
        """
        start_time = time.time()
        poll_interval = 2.0

        while time.time() - start_time < timeout:
            # Check if Unity is still importing/compiling
            is_importing = self._is_importing()
            is_compiling = self._is_compiling()

            if not is_importing and not is_compiling:
                # Check if the Switch Platform button is no longer disabled
                # or if the selected platform is now current
                time.sleep(1.0)
                if not self._is_importing() and not self._is_compiling():
                    return (True, "Platform switch completed")

            time.sleep(poll_interval)

        return (False, f"Timeout after {timeout} seconds")

    def _enter_build_output_path(self, output_path: str) -> bool:
        """
        Enter the output path in the build save dialog.

        Args:
            output_path: Path for the build output.

        Returns:
            True if path was entered successfully, False otherwise.
        """
        time.sleep(0.5)  # Wait for save dialog to appear

        # Use keyboard to enter path
        script = f'''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Handle the save dialog
                    -- Press Cmd+Shift+G to open "Go to folder" dialog
                    keystroke "g" using {{command down, shift down}}
                    delay 0.5

                    -- Clear any existing text and type the path
                    keystroke "a" using command down
                    delay 0.1
                    keystroke "{output_path}"
                    delay 0.3

                    -- Press Enter to go to the path
                    key code 36
                    delay 0.5

                    -- Press Enter again to confirm save
                    key code 36

                    return "success"
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _wait_for_build_complete(
        self,
        timeout: float = 600.0
    ) -> Tuple[bool, str, List[BuildError]]:
        """
        Wait for a build operation to complete.

        Uses log-based monitoring when available for more accurate build status
        detection and progress updates. Falls back to AppleScript-based polling.

        Args:
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (success, message, errors).
        """
        # Try log-based monitoring first (more accurate)
        log_monitor = self._get_log_monitor()
        if log_monitor is not None:
            return self._wait_for_build_with_log_monitor(log_monitor, timeout)

        # Fall back to AppleScript-based polling
        return self._wait_for_build_with_polling(timeout)

    def _wait_for_build_with_log_monitor(
        self,
        log_monitor: Any,
        timeout: float
    ) -> Tuple[bool, str, List[BuildError]]:
        """
        Wait for build completion using Unity Editor.log monitoring.

        Args:
            log_monitor: UnityLogMonitor instance.
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (success, message, errors).
        """
        errors: List[BuildError] = []

        # Set up progress callback if one is registered
        if self._build_progress_callback:
            def on_build_event(event: Any) -> None:
                if event.progress_percent is not None:
                    self._build_progress_callback(  # type: ignore
                        event.progress_percent,
                        event.message
                    )
            log_monitor.set_progress_callback(on_build_event)

        try:
            # Wait for build completion via log monitoring
            result = log_monitor.wait_for_build_completion(timeout_seconds=timeout)

            if result.success:
                return (True, "Build completed successfully", [])
            else:
                # Convert log monitor errors to BuildError objects
                for error_info in result.errors:
                    errors.append(BuildError(
                        message=error_info.message,
                        error_type=error_info.error_type,
                        file_path=error_info.file_path,
                        line_number=error_info.line_number,
                    ))

                if result.timed_out:
                    return (False, f"Build timeout after {timeout} seconds", errors)
                else:
                    return (False, "Build failed", errors)

        except Exception as e:
            logger.warning(f"Log monitoring failed, falling back to polling: {e}")
            # Fall back to polling if log monitoring fails
            return self._wait_for_build_with_polling(timeout)

    def _wait_for_build_with_polling(
        self,
        timeout: float
    ) -> Tuple[bool, str, List[BuildError]]:
        """
        Wait for build completion using AppleScript-based polling.

        This is the fallback method when log monitoring is not available.

        Args:
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (success, message, errors).
        """
        start_time = time.time()
        poll_interval = 2.0
        errors: List[BuildError] = []

        while time.time() - start_time < timeout:
            # Check for build completion indicators
            is_building = self._is_build_in_progress()

            if not is_building:
                # Check for build errors in Console
                build_errors = self._get_build_errors()
                if build_errors:
                    errors.extend(build_errors)
                    return (False, "Build failed with errors", errors)

                return (True, "Build completed successfully", [])

            # Check for build failure dialog
            if self._has_build_failed_dialog():
                error_msg = self._get_build_failure_message()
                errors.append(BuildError(
                    message=error_msg or "Build failed",
                    error_type="build"
                ))
                self._dismiss_build_failed_dialog()
                return (False, "Build failed", errors)

            time.sleep(poll_interval)

        return (False, f"Build timeout after {timeout} seconds", errors)

    def _is_build_in_progress(self) -> bool:
        """
        Check if a build is currently in progress.

        Returns:
            True if building, False otherwise.
        """
        # Check for build progress indicator or progress bar
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Check for progress bars
                    if exists progress indicator 1 of window 1 then
                        return "yes"
                    end if

                    -- Check window titles for build progress
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Building" or windowName contains "Build" then
                            if windowName contains "Progress" or windowName contains "%" then
                                return "yes"
                            end if
                        end if
                    end repeat

                    -- Check for "Compiling" indicator
                    set mainWindowName to name of window 1
                    if mainWindowName contains "Compiling" or mainWindowName contains "Building" then
                        return "yes"
                    end if

                    return "no"
                on error
                    return "no"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _has_build_failed_dialog(self) -> bool:
        """
        Check if a build failed dialog is visible.

        Returns:
            True if build failed dialog exists, False otherwise.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Build Failed" or windowName contains "Error" then
                            return "yes"
                        end if
                        -- Check for error text content
                        try
                            set windowText to value of static text 1 of w
                            if windowText contains "failed" or windowText contains "error" then
                                return "yes"
                            end if
                        end try
                    end repeat
                    return "no"
                on error
                    return "no"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "yes"

    def _get_build_failure_message(self) -> Optional[str]:
        """
        Get the error message from a build failure dialog.

        Returns:
            Error message if available, None otherwise.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Build" or windowName contains "Error" then
                            -- Try to get text content
                            try
                                set allText to ""
                                repeat with st in static texts of w
                                    set allText to allText & value of st & " "
                                end repeat
                                return allText
                            end try
                        end if
                    end repeat
                    return ""
                on error
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return output if success and output else None

    def _dismiss_build_failed_dialog(self) -> bool:
        """
        Dismiss a build failed dialog by clicking OK or Close.

        Returns:
            True if dialog was dismissed, False otherwise.
        """
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    repeat with w in windows
                        set windowName to name of w
                        if windowName contains "Build" or windowName contains "Error" then
                            -- Try clicking OK, Close, or any button
                            try
                                click button "OK" of w
                                return "success"
                            end try
                            try
                                click button "Close" of w
                                return "success"
                            end try
                            try
                                click button 1 of w
                                return "success"
                            end try
                        end if
                    end repeat
                    return "no_dialog"
                on error
                    return "error"
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        return success and output == "success"

    def _get_build_errors(self) -> List[BuildError]:
        """
        Get build errors from the Console window.

        Returns:
            List of BuildError objects.
        """
        errors: List[BuildError] = []

        # Try to read Console window content
        script = '''
        tell application "System Events"
            tell process "Unity"
                try
                    -- Look for Console window
                    set consoleText to ""
                    repeat with w in windows
                        if name of w contains "Console" then
                            -- Get all text from the Console
                            set allElements to entire contents of w
                            repeat with elem in allElements
                                try
                                    set elemText to value of elem as text
                                    if elemText contains "error" or elemText contains "Error" then
                                        set consoleText to consoleText & elemText & "|"
                                    end if
                                end try
                            end repeat
                        end if
                    end repeat
                    return consoleText
                on error
                    return ""
                end try
            end tell
        end tell
        '''

        success, output = self._run_applescript(script)
        if success and output:
            # Parse error messages
            parts = output.split("|")
            for part in parts:
                part = part.strip()
                if part and ("error" in part.lower() or "Error" in part):
                    # Determine error type
                    error_type = "unknown"
                    if "compilation" in part.lower() or "cs" in part.lower():
                        error_type = "compilation"
                    elif "asset" in part.lower():
                        error_type = "asset"
                    elif "manifest" in part.lower():
                        error_type = "manifest"
                    elif "signing" in part.lower() or "keystore" in part.lower():
                        error_type = "signing"

                    errors.append(BuildError(
                        message=part[:500],  # Limit message length
                        error_type=error_type
                    ))

        return errors

    # =========================================================================
    # Unity Menu Navigation
    # =========================================================================

    def navigate_menu(self, *menu_path: str) -> bool:
        """
        Navigate through Unity's menu system.

        Args:
            *menu_path: Sequence of menu items to click.
                       Example: ("File", "Build Settings...")

        Returns:
            True if navigation succeeded, False otherwise.

        Example:
            # Open Build Settings
            agent.navigate_menu("File", "Build Settings...")

            # Open Package Manager
            agent.navigate_menu("Window", "Package Manager")

            # Open Meta XR Setup Tool
            agent.navigate_menu("Meta", "Tools", "Project Setup Tool")
        """
        if not menu_path:
            return False

        if not self._activate_unity():
            return False

        # Build the AppleScript to click through menus
        script_parts = ['tell application "System Events"']
        script_parts.append('    tell process "Unity"')

        # Click the first menu item in menu bar
        script_parts.append(f'        click menu bar item "{menu_path[0]}" of menu bar 1')
        time.sleep(self.MENU_ANIMATION_DELAY)

        # Navigate through submenu items
        if len(menu_path) > 1:
            current_menu = f'menu "{menu_path[0]}" of menu bar item "{menu_path[0]}" of menu bar 1'

            for i, item in enumerate(menu_path[1:], 1):
                if i < len(menu_path) - 1:
                    # This is a submenu, click and descend
                    script_parts.append(f'        click menu item "{item}" of {current_menu}')
                    current_menu = f'menu "{item}" of menu item "{item}" of {current_menu}'
                else:
                    # This is the final menu item
                    script_parts.append(f'        click menu item "{item}" of {current_menu}')

        script_parts.append('    end tell')
        script_parts.append('end tell')

        script = '\n'.join(script_parts)

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False

    def open_menu_with_shortcut(self, key: str, modifiers: Optional[List[str]] = None) -> bool:
        """
        Open a menu or trigger an action using keyboard shortcut.

        Args:
            key: The key to press.
            modifiers: List of modifiers ("command", "option", "shift", "control").

        Returns:
            True if successful, False otherwise.
        """
        if modifiers is None:
            modifiers = []

        if not self._activate_unity():
            return False

        # Build modifier string for AppleScript
        modifier_str = ""
        if modifiers:
            modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"

        script = f'''
        tell application "System Events"
            tell process "Unity"
                keystroke "{key}"{modifier_str}
            end tell
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False

    # =========================================================================
    # Internal Helper Methods
    # =========================================================================

    def _activate_unity(self) -> bool:
        """
        Bring Unity to the foreground.

        Returns:
            True if Unity was activated, False otherwise.
        """
        if not self.is_unity_running():
            return False

        script = '''
        tell application "Unity" to activate
        delay 0.2
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False

    def _get_unity_window_title(self) -> Optional[str]:
        """Get the title of the main Unity window."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                if (count of windows) > 0 then
                    return name of window 1
                end if
            end tell
        end tell
        return ""
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip() or None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

        return None

    def _get_active_window_name(self) -> Optional[str]:
        """Get the name of the currently focused Unity window/tab."""
        script = '''
        tell application "System Events"
            tell process "Unity"
                if (count of windows) > 0 then
                    set frontWindow to window 1
                    return name of frontWindow
                end if
            end tell
        end tell
        return ""
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip() or None
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

        return None

    def _run_applescript(self, script: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Run an AppleScript and return the result.

        Args:
            script: The AppleScript to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            Tuple of (success, output).
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode == 0, result.stdout.strip())
        except subprocess.TimeoutExpired:
            return (False, "Timeout")
        except subprocess.SubprocessError as e:
            return (False, str(e))

    def _get_click_helper(self) -> Optional[Any]:
        """Get or create the ClickHelper instance for vision-based clicking."""
        if not CLICK_HELPER_AVAILABLE:
            return None

        if self._click_helper is None:
            try:
                self._click_helper = ClickHelper(
                    applescript_timeout=5.0,
                    min_vision_confidence=0.7,
                    enable_verification=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize ClickHelper: {e}")

        return self._click_helper

    def _get_screenshot_capture(self) -> Optional[Any]:
        """Get or create the MultiMonitorCapture instance for screenshots."""
        if not SCREENSHOT_AVAILABLE or not self._enable_multi_monitor:
            return None

        if self._screenshot_capture is None:
            try:
                self._screenshot_capture = MultiMonitorCapture()
            except Exception as e:
                logger.warning(f"Failed to initialize MultiMonitorCapture: {e}")

        return self._screenshot_capture

    def _get_log_monitor(self) -> Optional[Any]:
        """Get or create the UnityLogMonitor instance for build monitoring."""
        if not LOG_MONITOR_AVAILABLE or not self._enable_log_monitoring:
            return None

        if self._log_monitor is None:
            try:
                self._log_monitor = UnityLogMonitor()
            except Exception as e:
                logger.warning(f"Failed to initialize UnityLogMonitor: {e}")

        return self._log_monitor

    def _init_dialog_registry(self) -> None:
        """Initialize the dialog registry from YAML configuration."""
        if not DIALOG_REGISTRY_AVAILABLE:
            return

        try:
            if self._dialog_registry_path:
                self._dialog_registry = DialogRegistry.from_yaml(self._dialog_registry_path)
            else:
                # Try to load from default location
                self._dialog_registry = load_dialog_registry()
        except FileNotFoundError:
            # No custom config file, registry will use defaults
            self._dialog_registry = DialogRegistry()
            logger.debug("No dialog handlers config found, using defaults")
        except Exception as e:
            logger.warning(f"Failed to initialize DialogRegistry: {e}")
            self._dialog_registry = DialogRegistry()

    def _get_dialog_registry(self) -> Optional[Any]:
        """Get the DialogRegistry instance."""
        return self._dialog_registry if self._enable_dialog_registry else None

    # =========================================================================
    # Multi-Monitor Screenshot Capture
    # =========================================================================

    def capture_screenshot(
        self,
        all_displays: bool = True,
        display_id: Optional[int] = None
    ) -> Optional[bytes]:
        """
        Capture a screenshot from connected displays.

        Uses multi-monitor capture when available, falls back to single display.

        Args:
            all_displays: If True, capture and stitch all displays into panoramic view.
            display_id: If specified, capture only this display (ignored if all_displays=True).

        Returns:
            Screenshot as PNG bytes, or None if capture fails.

        Example:
            screenshot = agent.capture_screenshot()
            if screenshot:
                with open("debug.png", "wb") as f:
                    f.write(screenshot)
        """
        capture = self._get_screenshot_capture()
        if capture is None:
            logger.warning("Screenshot capture not available")
            return None

        try:
            if all_displays:
                result = capture.capture_all_displays()
                return result.image_bytes if result else None
            elif display_id is not None:
                result = capture.capture_display(display_id)
                return result.image_bytes if result else None
            else:
                # Capture primary display only
                result = capture.capture_primary_display()
                return result.image_bytes if result else None
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None

    def get_display_info(self) -> List[Any]:
        """
        Get information about all connected displays.

        Returns:
            List of DisplayInfo objects describing each display.

        Example:
            for display in agent.get_display_info():
                print(f"Display {display.display_id}: {display.bounds.width}x{display.bounds.height}")
        """
        capture = self._get_screenshot_capture()
        if capture is None:
            return []

        try:
            return capture.get_display_info()
        except Exception as e:
            logger.error(f"Failed to get display info: {e}")
            return []

    def screenshot_coords_to_screen(
        self,
        screenshot_x: float,
        screenshot_y: float
    ) -> Optional[Tuple[float, float]]:
        """
        Convert coordinates from screenshot pixel space to screen coordinate space.

        This is useful when using vision-based detection to find an element's
        position in a screenshot, then clicking at that position.

        Args:
            screenshot_x: X coordinate in the screenshot (pixels).
            screenshot_y: Y coordinate in the screenshot (pixels).

        Returns:
            Tuple of (screen_x, screen_y) or None if conversion fails.

        Example:
            # Find element position in screenshot using vision
            element_pos = (500, 300)  # Position in screenshot pixels
            screen_pos = agent.screenshot_coords_to_screen(*element_pos)
            if screen_pos:
                agent.click_at_coordinates(*screen_pos)
        """
        capture = self._get_screenshot_capture()
        if capture is None:
            return None

        try:
            return capture.screenshot_coords_to_screen(screenshot_x, screenshot_y)
        except Exception as e:
            logger.error(f"Coordinate conversion failed: {e}")
            return None

    # =========================================================================
    # Log-Based Build Monitoring
    # =========================================================================

    def set_build_progress_callback(
        self,
        callback: Optional[Callable[[float, str], None]]
    ) -> None:
        """
        Set a callback for build progress updates.

        The callback is called with (progress_percent, message) during builds.

        Args:
            callback: Function taking (float, str) or None to disable.

        Example:
            def on_progress(percent: float, message: str):
                print(f"Build: {percent:.0f}% - {message}")

            agent.set_build_progress_callback(on_progress)
            agent.build("builds/app.apk")
        """
        self._build_progress_callback = callback

    def _click_button(
        self,
        button_name: str,
        window_name: str = "",
        vision_fallback: Optional[bool] = None
    ) -> bool:
        """
        Click a button in Unity's UI.

        Args:
            button_name: Name/title of the button to click.
            window_name: Window to search in (empty string for default window).
            vision_fallback: If True, use vision-based detection on AppleScript failure.
                            If None, uses the agent's default setting.

        Returns:
            True if button was clicked, False otherwise.
        """
        use_vision_fallback = (
            vision_fallback if vision_fallback is not None
            else self._enable_vision_fallback
        )

        if window_name and window_name.strip():
            script = f'''
            tell application "System Events"
                tell process "Unity"
                    tell window "{window_name}"
                        click button "{button_name}"
                    end tell
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                tell process "Unity"
                    click button "{button_name}" of window 1
                end tell
            end tell
            '''

        success, _ = self._run_applescript(script)
        if success:
            logger.debug(f"AppleScript click succeeded for '{button_name}'")
            return True

        # AppleScript failed, try vision fallback if enabled
        if use_vision_fallback and CLICK_HELPER_AVAILABLE:
            logger.debug(f"AppleScript failed, trying vision fallback for '{button_name}'")
            return self._click_with_vision(button_name, window_name)

        return False

    def _click_with_vision(
        self,
        element_description: str,
        window_name: str = ""
    ) -> bool:
        """
        Click an element using vision-based detection.

        Args:
            element_description: Description of the element to click.
            window_name: Optional window context for the search.

        Returns:
            True if element was found and clicked, False otherwise.
        """
        click_helper = self._get_click_helper()
        if click_helper is None:
            logger.warning("ClickHelper not available for vision fallback")
            return False

        result = click_helper.click_element(
            app_name="Unity",
            element_description=element_description,
            window_name=window_name,
            vision_fallback=True,
            capture_verification=True
        )

        if result.success:
            logger.info(
                f"Vision click succeeded for '{element_description}' "
                f"at ({result.x}, {result.y}) with confidence {result.confidence:.2f}"
            )
        else:
            logger.warning(f"Vision click failed for '{element_description}': {result.error_message}")

        return result.success

    def click_element(
        self,
        element_description: str,
        window_name: str = "",
        vision_fallback: bool = True,
        capture_verification: bool = True
    ) -> Any:  # Returns ClickResult
        """
        Click a UI element in Unity with optional vision-based fallback.

        This is the recommended high-level method for clicking UI elements.
        It first attempts AppleScript-based clicking (fast path), then falls
        back to vision-based detection if enabled.

        Args:
            element_description: Description of the element to click.
                Can be a button name (for AppleScript) or natural language
                description (for vision-based detection).
            window_name: Optional window name to scope the search.
            vision_fallback: If True, use vision-based detection on AppleScript failure.
            capture_verification: If True, capture before/after screenshots for verification.

        Returns:
            ClickResult with success status, method used, coordinates, and optional
            verification screenshots.

        Example:
            result = agent.click_element("Build", "Build Settings")
            if result.success:
                print(f"Clicked via {result.method.value}")
        """
        if not CLICK_HELPER_AVAILABLE:
            # Fallback to basic click without detailed result
            success = self._click_button(button_name=element_description, window_name=window_name)
            # Return a basic result
            return ClickResult(
                success=success,
                method=ClickMethod.APPLESCRIPT if success else ClickMethod.FAILED,
                applescript_tried=True,
                error_message=None if success else "AppleScript click failed"
            )

        click_helper = self._get_click_helper()
        if click_helper is None:
            # Fallback
            success = self._click_button(
                button_name=element_description,
                window_name=window_name,
                vision_fallback=False
            )
            return ClickResult(
                success=success,
                method=ClickMethod.APPLESCRIPT if success else ClickMethod.FAILED,
                applescript_tried=True,
                error_message=None if success else "AppleScript click failed"
            )

        return click_helper.click_element(
            app_name="Unity",
            element_description=element_description,
            window_name=window_name,
            vision_fallback=vision_fallback,
            capture_verification=capture_verification
        )

    def _type_text(self, text: str) -> bool:
        """
        Type text into the currently focused field.

        Args:
            text: Text to type.

        Returns:
            True if successful, False otherwise.
        """
        script = f'''
        tell application "System Events"
            tell process "Unity"
                keystroke "{text}"
            end tell
        end tell
        '''

        success, _ = self._run_applescript(script)
        return success

    def _press_key(self, key_code: int, modifiers: Optional[List[str]] = None) -> bool:
        """
        Press a key by key code.

        Args:
            key_code: The key code to press.
            modifiers: Optional list of modifiers.

        Returns:
            True if successful, False otherwise.
        """
        if modifiers is None:
            modifiers = []

        modifier_str = ""
        if modifiers:
            modifier_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"

        script = f'''
        tell application "System Events"
            tell process "Unity"
                key code {key_code}{modifier_str}
            end tell
        end tell
        '''

        success, _ = self._run_applescript(script)
        return success

    # =========================================================================
    # Vision-Based Automation Methods (GUI-009)
    # =========================================================================

    def _get_panel_detector(self) -> Optional[Any]:
        """
        Get or create the UnityPanelDetector instance for vision-based panel operations.

        Returns:
            UnityPanelDetector instance if available, None otherwise.
        """
        if not UNITY_PANELS_AVAILABLE:
            logger.warning("UnityPanelDetector not available - unity_panels module not installed")
            return None

        # Lazy initialization
        if not hasattr(self, '_panel_detector'):
            try:
                self._panel_detector = UnityPanelDetector()  # type: ignore[misc]
            except Exception as e:
                logger.error(f"Failed to initialize UnityPanelDetector: {e}")
                return None

        return self._panel_detector

    def _get_wait_helper(self) -> Optional[Any]:
        """
        Get or create the WaitHelper instance for vision-based waiting operations.

        Returns:
            WaitHelper instance if available, None otherwise.
        """
        if not WAIT_UTILS_AVAILABLE:
            logger.warning("WaitHelper not available - wait_utils module not installed")
            return None

        # Lazy initialization
        if not hasattr(self, '_wait_helper'):
            try:
                self._wait_helper = WaitHelper()  # type: ignore[misc]
            except Exception as e:
                logger.error(f"Failed to initialize WaitHelper: {e}")
                return None

        return self._wait_helper

    def _get_vision_detector(self) -> Optional[Any]:
        """
        Get or create the VisionDetector instance for element state detection.

        Returns:
            VisionDetector instance if available, None otherwise.
        """
        if not VISION_DETECTOR_AVAILABLE:
            logger.warning("VisionDetector not available - vision_detector module not installed")
            return None

        # Lazy initialization
        if not hasattr(self, '_vision_detector'):
            try:
                self._vision_detector = VisionDetector()  # type: ignore[misc]
            except Exception as e:
                logger.error(f"Failed to initialize VisionDetector: {e}")
                return None

        return self._vision_detector

    def add_building_block(
        self,
        block_name: str,
        timeout: float = 10.0,
        capture_screenshots: bool = True,
    ) -> VisionWorkflowResult:
        """
        Add a building block from the Meta Building Blocks panel using vision-based clicking.

        This method:
        1. Opens the Building Blocks panel if not visible
        2. Uses vision API to find the specified block
        3. Clicks the block to add it to the scene
        4. Verifies the block was added

        Args:
            block_name: Name of the building block to add (e.g., "Camera Rig",
                       "Passthrough", "Hand Tracking").
            timeout: Maximum time to wait for the panel/block to appear.
            capture_screenshots: If True, capture before/after screenshots.

        Returns:
            VisionWorkflowResult with success status and details.

        Example:
            result = agent.add_building_block("Camera Rig")
            if result.success:
                print(f"Added Camera Rig building block")
            else:
                print(f"Failed: {result.error}")
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None

        # Verify required modules are available
        panel_detector = self._get_panel_detector()
        if panel_detector is None:
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.NOT_AVAILABLE,
                message="Vision-based panel detection not available",
                error="UnityPanelDetector module not installed",
            )

        # Capture before screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_before = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture before screenshot: {e}")

        # Check if Building Blocks panel is open
        panel_name = "Building Blocks"
        if not panel_detector.is_panel_open(panel_name):
            # Try to open Building Blocks panel via menu
            logger.info(f"Opening {panel_name} panel via menu")
            self.navigate_menu("Window", "Meta", "Building Blocks")
            time.sleep(0.5)

            # Wait for panel to appear
            wait_result = panel_detector.wait_for_panel(panel_name, timeout=timeout)
            if not wait_result.found:
                duration_ms = int((time.time() - start_time) * 1000)
                return VisionWorkflowResult(
                    success=False,
                    status=VisionWorkflowStatus.PANEL_NOT_FOUND,
                    message=f"Could not find {panel_name} panel",
                    duration_ms=duration_ms,
                    error="Panel did not appear after opening via menu",
                    screenshot_before=screenshot_before,
                )

        # Click the building block button within the panel
        logger.info(f"Clicking building block: {block_name}")
        click_result = panel_detector.click_button_in_panel(panel_name, block_name)

        if not click_result.success:
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.BUTTON_NOT_FOUND,
                message=f"Could not find or click '{block_name}' in {panel_name}",
                duration_ms=duration_ms,
                error=click_result.error_message,
                screenshot_before=screenshot_before,
                details={
                    "panel_name": panel_name,
                    "block_name": block_name,
                },
            )

        # Wait briefly for the action to complete
        time.sleep(0.5)

        # Capture after screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_after = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture after screenshot: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        return VisionWorkflowResult(
            success=True,
            status=VisionWorkflowStatus.SUCCESS,
            message=f"Successfully added building block '{block_name}'",
            duration_ms=duration_ms,
            details={
                "panel_name": panel_name,
                "block_name": block_name,
                "click_x": click_result.x,
                "click_y": click_result.y,
                "confidence": click_result.confidence,
            },
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

    def run_project_setup_fix_all(
        self,
        timeout: float = 30.0,
        capture_screenshots: bool = True,
    ) -> VisionWorkflowResult:
        """
        Run the Project Setup Tool's "Fix All" action using vision-based clicking.

        This method:
        1. Opens the Project Setup Tool panel if not visible
        2. Uses vision API to find the "Fix All" button
        3. Clicks "Fix All" to fix all issues
        4. Waits for the fixes to be applied
        5. Verifies the result

        Args:
            timeout: Maximum time to wait for the panel and fixes.
            capture_screenshots: If True, capture before/after screenshots.

        Returns:
            VisionWorkflowResult with success status and details.

        Example:
            result = agent.run_project_setup_fix_all()
            if result.success:
                print("All project setup issues fixed")
            else:
                print(f"Fix All failed: {result.error}")
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None

        # Verify required modules are available
        panel_detector = self._get_panel_detector()
        if panel_detector is None:
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.NOT_AVAILABLE,
                message="Vision-based panel detection not available",
                error="UnityPanelDetector module not installed",
            )

        # Capture before screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_before = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture before screenshot: {e}")

        # Check if Project Setup Tool panel is open
        panel_name = "Project Setup Tool"
        if not panel_detector.is_panel_open(panel_name):
            # Try to open Project Setup Tool via menu
            logger.info(f"Opening {panel_name} panel via menu")
            self.navigate_menu("Oculus", "Tools", "Project Setup Tool")
            time.sleep(0.5)

            # Wait for panel to appear
            wait_result = panel_detector.wait_for_panel(panel_name, timeout=timeout / 2)
            if not wait_result.found:
                duration_ms = int((time.time() - start_time) * 1000)
                return VisionWorkflowResult(
                    success=False,
                    status=VisionWorkflowStatus.PANEL_NOT_FOUND,
                    message=f"Could not find {panel_name} panel",
                    duration_ms=duration_ms,
                    error="Panel did not appear after opening via menu",
                    screenshot_before=screenshot_before,
                )

        # Click the "Fix All" button within the panel
        logger.info("Clicking 'Fix All' button in Project Setup Tool")
        click_result = panel_detector.click_button_in_panel(panel_name, "Fix All")

        if not click_result.success:
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.BUTTON_NOT_FOUND,
                message="Could not find or click 'Fix All' button",
                duration_ms=duration_ms,
                error=click_result.error_message,
                screenshot_before=screenshot_before,
                details={
                    "panel_name": panel_name,
                },
            )

        # Wait for fixes to be applied (Unity may need to recompile)
        logger.info("Waiting for fixes to be applied...")
        time.sleep(2.0)

        # Wait for Unity to finish any compilation/import operations
        self.wait_for_idle(timeout=timeout / 2)

        # Capture after screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_after = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture after screenshot: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        return VisionWorkflowResult(
            success=True,
            status=VisionWorkflowStatus.SUCCESS,
            message="Successfully clicked 'Fix All' in Project Setup Tool",
            duration_ms=duration_ms,
            details={
                "panel_name": panel_name,
                "click_x": click_result.x,
                "click_y": click_result.y,
                "confidence": click_result.confidence,
            },
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

    def run_project_setup_apply_all(
        self,
        timeout: float = 30.0,
        capture_screenshots: bool = True,
    ) -> VisionWorkflowResult:
        """
        Run the Project Setup Tool's "Apply All" action using vision-based clicking.

        Similar to fix_all but clicks "Apply All" button. Some Unity project setup
        tools use "Apply All" instead of "Fix All" for applying recommended settings.

        Args:
            timeout: Maximum time to wait for the panel and application.
            capture_screenshots: If True, capture before/after screenshots.

        Returns:
            VisionWorkflowResult with success status and details.

        Example:
            result = agent.run_project_setup_apply_all()
            if result.success:
                print("All project setup settings applied")
            else:
                print(f"Apply All failed: {result.error}")
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None

        # Verify required modules are available
        panel_detector = self._get_panel_detector()
        if panel_detector is None:
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.NOT_AVAILABLE,
                message="Vision-based panel detection not available",
                error="UnityPanelDetector module not installed",
            )

        # Capture before screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_before = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture before screenshot: {e}")

        # Check if Project Setup Tool panel is open
        panel_name = "Project Setup Tool"
        if not panel_detector.is_panel_open(panel_name):
            # Try to open Project Setup Tool via menu
            logger.info(f"Opening {panel_name} panel via menu")
            self.navigate_menu("Oculus", "Tools", "Project Setup Tool")
            time.sleep(0.5)

            # Wait for panel to appear
            wait_result = panel_detector.wait_for_panel(panel_name, timeout=timeout / 2)
            if not wait_result.found:
                duration_ms = int((time.time() - start_time) * 1000)
                return VisionWorkflowResult(
                    success=False,
                    status=VisionWorkflowStatus.PANEL_NOT_FOUND,
                    message=f"Could not find {panel_name} panel",
                    duration_ms=duration_ms,
                    error="Panel did not appear after opening via menu",
                    screenshot_before=screenshot_before,
                )

        # Click the "Apply All" button within the panel
        logger.info("Clicking 'Apply All' button in Project Setup Tool")
        click_result = panel_detector.click_button_in_panel(panel_name, "Apply All")

        if not click_result.success:
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.BUTTON_NOT_FOUND,
                message="Could not find or click 'Apply All' button",
                duration_ms=duration_ms,
                error=click_result.error_message,
                screenshot_before=screenshot_before,
                details={
                    "panel_name": panel_name,
                },
            )

        # Wait for settings to be applied
        logger.info("Waiting for settings to be applied...")
        time.sleep(2.0)

        # Wait for Unity to finish any compilation/import operations
        self.wait_for_idle(timeout=timeout / 2)

        # Capture after screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_after = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture after screenshot: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        return VisionWorkflowResult(
            success=True,
            status=VisionWorkflowStatus.SUCCESS,
            message="Successfully clicked 'Apply All' in Project Setup Tool",
            duration_ms=duration_ms,
            details={
                "panel_name": panel_name,
                "click_x": click_result.x,
                "click_y": click_result.y,
                "confidence": click_result.confidence,
            },
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

    def verify_panel_state(
        self,
        panel_name: str,
        check_for_errors: bool = True,
        check_for_warnings: bool = True,
    ) -> PanelStateResult:
        """
        Verify the state of a Unity panel, checking for errors and warnings.

        Uses vision-based detection to check if a panel is visible and analyze
        its contents for error indicators (red text, error icons, etc.).

        Args:
            panel_name: Name of the panel to check (e.g., "Console", "Inspector",
                       "Project Setup Tool").
            check_for_errors: If True, look for error indicators.
            check_for_warnings: If True, look for warning indicators.

        Returns:
            PanelStateResult with panel state and any errors/warnings found.

        Example:
            result = agent.verify_panel_state("Console")
            if result.has_errors:
                print(f"Found {result.error_count} errors in Console")
                for msg in result.error_messages:
                    print(f"  - {msg}")
        """
        # Verify required modules are available
        panel_detector = self._get_panel_detector()
        if panel_detector is None:
            return PanelStateResult(
                panel_found=False,
                panel_name=panel_name,
                error="UnityPanelDetector module not available",
            )

        vision_detector = self._get_vision_detector()
        if vision_detector is None:
            return PanelStateResult(
                panel_found=False,
                panel_name=panel_name,
                error="VisionDetector module not available",
            )

        # Check if panel is visible
        if not panel_detector.is_panel_open(panel_name):
            return PanelStateResult(
                panel_found=False,
                panel_name=panel_name,
                error=f"Panel '{panel_name}' is not visible",
            )

        # Get panel bounds
        bounds_result = panel_detector.get_panel_bounds(panel_name)
        panel_bounds = None
        if bounds_result and bounds_result.bounds:
            panel_bounds = bounds_result.bounds.to_dict()

        # Take a screenshot to analyze
        if not SCREENSHOT_AVAILABLE:
            return PanelStateResult(
                panel_found=True,
                panel_name=panel_name,
                panel_bounds=panel_bounds,
                error="Screenshot capture not available for state analysis",
            )

        try:
            capture = self._get_screenshot_capture()
            if not capture:
                return PanelStateResult(
                    panel_found=True,
                    panel_name=panel_name,
                    panel_bounds=panel_bounds,
                    error="Failed to initialize screenshot capture",
                )

            screenshot = capture.capture_all_displays()
            if not screenshot or not screenshot.combined_image:
                return PanelStateResult(
                    panel_found=True,
                    panel_name=panel_name,
                    panel_bounds=panel_bounds,
                    error="Failed to capture screenshot for analysis",
                )

            # Use vision detector to analyze the panel for errors/warnings
            error_messages: List[str] = []
            warning_messages: List[str] = []

            if check_for_errors:
                # Look for error indicators in the panel
                error_result = vision_detector.get_error_message(
                    screenshot.combined_image,
                    f"error message or red text in the {panel_name} panel"
                )
                if error_result and error_result.error_text:
                    error_messages.append(error_result.error_text)

            if check_for_warnings:
                # Look for warning indicators in the panel
                warning_result = vision_detector.get_status_text(
                    screenshot.combined_image,
                    f"warning message or yellow text in the {panel_name} panel"
                )
                if warning_result and warning_result.status_text:
                    # Check if it looks like a warning (yellow, contains "warning", etc.)
                    status_lower = warning_result.status_text.lower()
                    if "warning" in status_lower or "caution" in status_lower:
                        warning_messages.append(warning_result.status_text)

            return PanelStateResult(
                panel_found=True,
                panel_name=panel_name,
                has_errors=len(error_messages) > 0,
                has_warnings=len(warning_messages) > 0,
                error_count=len(error_messages),
                warning_count=len(warning_messages),
                error_messages=error_messages,
                warning_messages=warning_messages,
                panel_bounds=panel_bounds,
            )

        except Exception as e:
            logger.error(f"Error analyzing panel state: {e}")
            return PanelStateResult(
                panel_found=True,
                panel_name=panel_name,
                panel_bounds=panel_bounds,
                error=f"Failed to analyze panel state: {e}",
            )

    def save_scene_vision(
        self,
        scene_name: Optional[str] = None,
        timeout: float = 10.0,
        capture_screenshots: bool = True,
    ) -> VisionWorkflowResult:
        """
        Save the current scene with vision-based verification.

        This method:
        1. Triggers save via keyboard shortcut (Cmd+S)
        2. Handles any save dialog that appears
        3. Verifies the save completed successfully
        4. Uses vision API to detect save dialogs and verify completion

        Args:
            scene_name: Optional name for a new scene. If None, saves current scene.
            timeout: Maximum time to wait for save operation.
            capture_screenshots: If True, capture before/after screenshots.

        Returns:
            VisionWorkflowResult with success status and details.

        Example:
            result = agent.save_scene_vision()
            if result.success:
                print("Scene saved successfully")
            else:
                print(f"Save failed: {result.error}")
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None

        # Capture before screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_before = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture before screenshot: {e}")

        # Ensure Unity is focused
        if not self._activate_unity():
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.FAILED,
                message="Failed to activate Unity",
                duration_ms=duration_ms,
                error="Could not bring Unity to foreground",
                screenshot_before=screenshot_before,
            )

        # Trigger save via menu (more reliable than keyboard shortcut)
        logger.info("Triggering scene save via menu")
        if not self.navigate_menu("File", "Save"):
            # Try keyboard shortcut as fallback
            logger.info("Menu navigation failed, trying Cmd+S")
            self._press_key(1, ["command"])  # Key code 1 is 'S' on macOS

        # Wait for potential save dialog
        time.sleep(0.5)

        # Check for save dialog using vision if available
        wait_helper = self._get_wait_helper()
        if wait_helper:
            # Wait for any save-related dialog or for the save to complete
            # We'll look for "save" text to disappear (indicating save completed)
            try:
                # Wait briefly for save to complete (usually instant for existing scenes)
                time.sleep(1.0)
            except Exception as e:
                logger.warning(f"Wait helper error: {e}")

        # Handle "Save Scene As" dialog if it appears (for new scenes)
        if scene_name:
            panel_detector = self._get_panel_detector()
            if panel_detector:
                # Check if save dialog appeared
                if panel_detector.is_panel_open("Save Scene"):
                    # Type the scene name
                    self._type_text(scene_name)
                    time.sleep(0.2)
                    # Press Enter to confirm
                    self._press_key(36)  # Enter key

        # Wait for any file operations to complete
        time.sleep(0.5)

        # Capture after screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_after = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture after screenshot: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        return VisionWorkflowResult(
            success=True,
            status=VisionWorkflowStatus.SUCCESS,
            message="Scene save triggered successfully",
            duration_ms=duration_ms,
            details={
                "scene_name": scene_name or "current scene",
            },
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

    def build_apk_vision(
        self,
        output_path: Optional[str] = None,
        timeout: float = 600.0,  # 10 minutes default
        progress_callback: Optional[Callable[[BuildProgressInfo], None]] = None,
        capture_screenshots: bool = True,
    ) -> VisionWorkflowResult:
        """
        Build an Android APK with vision-based progress detection.

        This method:
        1. Opens Build Settings if not already open
        2. Verifies Android platform is selected
        3. Clicks the "Build" button
        4. Monitors build progress using vision API
        5. Detects build completion or errors
        6. Returns detailed result with progress information

        Args:
            output_path: Optional path for the APK output. If None, Unity will
                        prompt for a save location.
            timeout: Maximum time to wait for build completion.
            progress_callback: Optional callback for build progress updates.
            capture_screenshots: If True, capture periodic screenshots during build.

        Returns:
            VisionWorkflowResult with build status, progress info, and any errors.

        Example:
            def on_progress(info):
                print(f"Build progress: {info.phase} - {info.progress_percent}%")

            result = agent.build_apk_vision(progress_callback=on_progress)
            if result.success:
                print("APK built successfully!")
            else:
                print(f"Build failed: {result.error}")
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None
        build_errors: List[str] = []
        build_warnings: List[str] = []

        # Capture before screenshot if enabled
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_before = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture before screenshot: {e}")

        # Ensure Unity is focused
        if not self._activate_unity():
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.FAILED,
                message="Failed to activate Unity",
                duration_ms=duration_ms,
                error="Could not bring Unity to foreground",
                screenshot_before=screenshot_before,
            )

        # Open Build Settings
        logger.info("Opening Build Settings")
        if not self.navigate_menu("File", "Build Settings..."):
            duration_ms = int((time.time() - start_time) * 1000)
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.FAILED,
                message="Failed to open Build Settings",
                duration_ms=duration_ms,
                error="Could not navigate to Build Settings menu",
                screenshot_before=screenshot_before,
            )

        # Wait for Build Settings window to appear
        time.sleep(1.0)

        panel_detector = self._get_panel_detector()
        vision_detector = self._get_vision_detector()

        # Try to verify Android platform is selected using vision
        if panel_detector and panel_detector.is_panel_open("Build Settings"):
            # Click the "Build" button using vision
            logger.info("Clicking 'Build' button in Build Settings")
            click_result = panel_detector.click_button_in_panel("Build Settings", "Build")

            if not click_result.success:
                # Try clicking "Build And Run" as fallback
                click_result = panel_detector.click_button_in_panel("Build Settings", "Build And Run")

                if not click_result.success:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return VisionWorkflowResult(
                        success=False,
                        status=VisionWorkflowStatus.BUTTON_NOT_FOUND,
                        message="Could not find Build button",
                        duration_ms=duration_ms,
                        error=click_result.error_message,
                        screenshot_before=screenshot_before,
                    )
        else:
            # Fall back to AppleScript click
            logger.info("Using AppleScript to click Build button")
            if not self._click_button("Build", "Build Settings"):
                duration_ms = int((time.time() - start_time) * 1000)
                return VisionWorkflowResult(
                    success=False,
                    status=VisionWorkflowStatus.BUTTON_NOT_FOUND,
                    message="Could not click Build button",
                    duration_ms=duration_ms,
                    error="Both vision and AppleScript click failed",
                    screenshot_before=screenshot_before,
                )

        # Wait for save dialog and handle output path
        time.sleep(1.0)
        if output_path:
            # Type the output path if provided
            self._type_text(output_path)
            time.sleep(0.2)
            self._press_key(36)  # Enter key

        # Monitor build progress
        logger.info("Monitoring build progress...")
        build_start = time.time()
        last_progress_update = time.time()
        progress_update_interval = 5.0  # Update progress every 5 seconds

        while (time.time() - build_start) < timeout:
            elapsed = time.time() - build_start

            # Report progress periodically
            if progress_callback and (time.time() - last_progress_update) >= progress_update_interval:
                progress_info = BuildProgressInfo(
                    phase="building",
                    progress_percent=min(elapsed / timeout * 100, 99),
                    elapsed_seconds=elapsed,
                    errors=build_errors,
                    warnings=build_warnings,
                )
                progress_callback(progress_info)
                last_progress_update = time.time()

            # Check for build completion or errors using vision
            if vision_detector and SCREENSHOT_AVAILABLE:
                try:
                    capture = self._get_screenshot_capture()
                    if capture:
                        screenshot = capture.capture_all_displays()
                        if screenshot and screenshot.combined_image:
                            # Look for "Build successful" or "Build completed" text
                            status = vision_detector.get_status_text(
                                screenshot.combined_image,
                                "Build complete, Build successful, or Build finished message"
                            )
                            if status and status.status_text:
                                status_lower = status.status_text.lower()
                                if "success" in status_lower or "complete" in status_lower or "finished" in status_lower:
                                    logger.info(f"Build completed: {status.status_text}")
                                    break

                            # Look for build errors
                            error = vision_detector.get_error_message(
                                screenshot.combined_image,
                                "Build failed, Build error, or compilation error"
                            )
                            if error and error.error_text:
                                error_lower = error.error_text.lower()
                                if "failed" in error_lower or "error" in error_lower:
                                    build_errors.append(error.error_text)
                                    # Check if it's a fatal error
                                    if "build failed" in error_lower:
                                        logger.error(f"Build failed: {error.error_text}")
                                        break
                except Exception as e:
                    logger.warning(f"Error checking build progress: {e}")

            # Also check if Unity is still busy (compiling/building)
            if not self._is_busy():
                # Unity is idle, build might be complete or failed
                time.sleep(1.0)  # Brief wait to ensure stability
                if not self._is_busy():
                    break

            time.sleep(1.0)  # Poll interval

        # Capture after screenshot
        if capture_screenshots and SCREENSHOT_AVAILABLE:
            try:
                capture = self._get_screenshot_capture()
                if capture:
                    screenshot = capture.capture_all_displays()
                    screenshot_after = screenshot.combined_image
            except Exception as e:
                logger.warning(f"Failed to capture after screenshot: {e}")

        # Determine build result
        duration_ms = int((time.time() - start_time) * 1000)
        elapsed_seconds = (time.time() - build_start)

        if elapsed_seconds >= timeout:
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.TIMEOUT,
                message="Build timed out",
                duration_ms=duration_ms,
                error=f"Build did not complete within {timeout} seconds",
                details={
                    "elapsed_seconds": elapsed_seconds,
                    "errors": build_errors,
                    "warnings": build_warnings,
                },
                screenshot_before=screenshot_before,
                screenshot_after=screenshot_after,
            )

        if build_errors:
            return VisionWorkflowResult(
                success=False,
                status=VisionWorkflowStatus.FAILED,
                message="Build failed with errors",
                duration_ms=duration_ms,
                error="; ".join(build_errors),
                details={
                    "elapsed_seconds": elapsed_seconds,
                    "errors": build_errors,
                    "warnings": build_warnings,
                },
                screenshot_before=screenshot_before,
                screenshot_after=screenshot_after,
            )

        # Report final progress
        if progress_callback:
            progress_info = BuildProgressInfo(
                phase="complete",
                progress_percent=100.0,
                elapsed_seconds=elapsed_seconds,
                errors=build_errors,
                warnings=build_warnings,
            )
            progress_callback(progress_info)

        return VisionWorkflowResult(
            success=True,
            status=VisionWorkflowStatus.SUCCESS,
            message="APK build completed successfully",
            duration_ms=duration_ms,
            details={
                "elapsed_seconds": elapsed_seconds,
                "output_path": output_path,
                "warnings": build_warnings,
            },
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

    def _is_busy(self) -> bool:
        """
        Check if Unity is currently busy (compiling, importing, or building).

        Returns:
            True if Unity is busy, False if idle.
        """
        return self._is_compiling() or self._is_importing()


# =============================================================================
# Workflow Orchestrator
# =============================================================================


class WorkflowStep(Enum):
    """Steps in Unity automation workflows."""
    # Setup Quest 3 workflow steps
    CHECK_UNITY = "check_unity"
    INSTALL_META_SDK = "install_meta_sdk"
    WAIT_FOR_IMPORT = "wait_for_import"
    CONFIGURE_XR = "configure_xr"
    RUN_META_SETUP = "run_meta_setup"
    ADD_DEFINE_SYMBOLS = "add_define_symbols"
    WAIT_FOR_RECOMPILE = "wait_for_recompile"
    BUILD_APK = "build_apk"
    DEPLOY_TO_DEVICE = "deploy_to_device"
    # Common steps
    HANDLE_DIALOGS = "handle_dialogs"
    COMPLETE = "complete"
    FAILED = "failed"


class WorkflowStatus(Enum):
    """Status of a workflow execution."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowProgress:
    """Progress update for workflow callbacks."""
    step: WorkflowStep
    status: WorkflowStatus
    message: str
    progress_percent: float = 0.0
    step_number: int = 0
    total_steps: int = 0
    details: Optional[dict] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        pct = f"{self.progress_percent:.0f}%" if self.progress_percent > 0 else ""
        step_info = f"[{self.step_number}/{self.total_steps}]" if self.total_steps > 0 else ""
        return f"{step_info} {self.step.value}: {self.message} {pct}".strip()


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    success: bool
    workflow_name: str
    message: str
    duration_seconds: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    errors: Optional[List[str]] = None
    details: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.details is None:
            self.details = {}


# Type alias for progress callback
ProgressCallback = Optional[Callable[["WorkflowProgress"], Any]]


class UnityWorkflows:
    """
    High-level workflow orchestrator for Unity automation.

    Provides compound operations that combine multiple UnityAgent methods
    into complete workflows for common tasks like Quest 3 project setup.

    All workflows support optional progress callbacks for status updates.

    Example:
        from agents.computer_use.unity import UnityWorkflows

        workflows = UnityWorkflows()

        # With progress callback
        def on_progress(progress: WorkflowProgress):
            print(f"{progress}")

        result = workflows.setup_quest3_project(
            progress_callback=on_progress
        )

        if result.success:
            print(f"Setup complete in {result.duration_seconds:.1f}s")
        else:
            print(f"Setup failed: {result.message}")
    """

    # Meta XR SDK package name for Asset Store
    META_XR_SDK_PACKAGE_NAME = "Meta XR All-in-One SDK"
    META_XR_SDK_PACKAGE_ALT_NAMES = [
        "Meta XR SDK",
        "Oculus Integration",
        "Meta XR All-in-One",
    ]

    # Default scripting define symbol for Quest development
    QUEST_DEFINE_SYMBOL = "OCULUS_XR_SDK"

    def __init__(
        self,
        agent: Optional[UnityAgent] = None,
        enable_checkpointing: bool = True,
        checkpoint_dir: Optional[str] = None
    ):
        """
        Initialize the workflow orchestrator.

        Args:
            agent: Optional UnityAgent instance. Creates new one if not provided.
            enable_checkpointing: If True, save progress checkpoints during workflows.
            checkpoint_dir: Optional custom directory for checkpoints.
        """
        self._agent = agent or UnityAgent()
        self._cancelled = False

        # Checkpointing support
        self._enable_checkpointing = enable_checkpointing and CHECKPOINT_AVAILABLE
        self._checkpoint: Optional[Any] = None  # WorkflowCheckpoint when available
        self._checkpoint_dir = checkpoint_dir
        self._current_workflow_id: Optional[str] = None

    @property
    def agent(self) -> UnityAgent:
        """Get the underlying UnityAgent instance."""
        return self._agent

    def cancel(self) -> None:
        """Cancel the current workflow (if running)."""
        self._cancelled = True

    def _reset_cancel(self) -> None:
        """Reset the cancel flag for a new workflow."""
        self._cancelled = False

    def _is_cancelled(self) -> bool:
        """Check if workflow should be cancelled."""
        return self._cancelled

    def _init_checkpoint(self, workflow_id: str) -> None:
        """Initialize checkpoint manager for a workflow."""
        if not self._enable_checkpointing or not CHECKPOINT_AVAILABLE:
            return

        self._current_workflow_id = workflow_id
        try:
            self._checkpoint = WorkflowCheckpoint(
                workflow_id=workflow_id,
                checkpoint_dir=self._checkpoint_dir
            )
        except Exception as e:
            logger.warning(f"Failed to initialize checkpointing: {e}")
            self._checkpoint = None

    def _save_checkpoint(
        self,
        step_id: str,
        context: Optional[dict] = None
    ) -> None:
        """
        Save a checkpoint after a workflow step.

        Args:
            step_id: Identifier for the completed step.
            context: Optional context data to restore state.
        """
        if self._checkpoint is None:
            return

        try:
            self._checkpoint.save(
                step_id=step_id,
                context=context or {}
            )
            logger.debug(f"Checkpoint saved: {step_id}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _get_resume_step(self) -> Optional[str]:
        """
        Get the step ID to resume from if a checkpoint exists.

        Returns:
            Step ID to resume from, or None to start from beginning.
        """
        if self._checkpoint is None:
            return None

        try:
            if self._checkpoint.has_checkpoint():
                data = self._checkpoint.load_latest()
                if data:
                    return data.step_id
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

        return None

    def _cleanup_checkpoints(self) -> None:
        """Clean up checkpoints after successful workflow completion."""
        if self._checkpoint is None:
            return

        try:
            self._checkpoint.cleanup()
            logger.debug("Checkpoints cleaned up")
        except Exception as e:
            logger.warning(f"Failed to cleanup checkpoints: {e}")

    def _report_progress(
        self,
        callback: ProgressCallback,
        step: WorkflowStep,
        status: WorkflowStatus,
        message: str,
        progress_percent: float = 0.0,
        step_number: int = 0,
        total_steps: int = 0,
        details: Optional[dict] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Report progress to the callback if provided.

        Args:
            callback: Optional progress callback function.
            step: Current workflow step.
            status: Current status.
            message: Human-readable status message.
            progress_percent: Overall progress percentage (0-100).
            step_number: Current step number.
            total_steps: Total number of steps.
            details: Optional additional details.
            error: Optional error message.
        """
        if callback is None:
            return

        progress = WorkflowProgress(
            step=step,
            status=status,
            message=message,
            progress_percent=progress_percent,
            step_number=step_number,
            total_steps=total_steps,
            details=details,
            error=error
        )

        try:
            callback(progress)
        except Exception:
            # Don't let callback errors break the workflow
            pass

    # =========================================================================
    # install_meta_xr_sdk - Install Meta XR SDK from Asset Store
    # =========================================================================

    def install_meta_xr_sdk(
        self,
        package_name: Optional[str] = None,
        progress_callback: ProgressCallback = None
    ) -> WorkflowResult:
        """
        Download and install the Meta XR SDK from the Asset Store.

        This workflow:
        1. Opens Package Manager
        2. Searches for Meta XR SDK in My Assets
        3. Downloads and imports the package
        4. Handles any dialogs that appear (Input System, API Update, etc.)
        5. Waits for import to complete

        Args:
            package_name: Optional package name override. Defaults to Meta XR All-in-One SDK.
            progress_callback: Optional callback for progress updates.

        Returns:
            WorkflowResult with success status and details.
        """
        import time as time_module
        start_time = time_module.time()
        self._reset_cancel()

        pkg_name = package_name or self.META_XR_SDK_PACKAGE_NAME
        total_steps = 5
        errors: List[str] = []

        # Step 1: Check Unity is running
        self._report_progress(
            progress_callback, WorkflowStep.CHECK_UNITY, WorkflowStatus.IN_PROGRESS,
            "Checking Unity status...", 0, 1, total_steps
        )

        if not self._agent.is_unity_running():
            return WorkflowResult(
                success=False,
                workflow_name="install_meta_xr_sdk",
                message="Unity is not running",
                duration_seconds=time_module.time() - start_time,
                steps_completed=0,
                steps_total=total_steps,
                errors=["Unity Editor must be running to install packages"]
            )

        if self._is_cancelled():
            return self._cancelled_result("install_meta_xr_sdk", start_time, 1, total_steps)

        # Step 2: Open Package Manager
        self._report_progress(
            progress_callback, WorkflowStep.INSTALL_META_SDK, WorkflowStatus.IN_PROGRESS,
            "Opening Package Manager...", 20, 2, total_steps
        )

        if not self._agent.open_package_manager():
            errors.append("Failed to open Package Manager")
            return WorkflowResult(
                success=False,
                workflow_name="install_meta_xr_sdk",
                message="Failed to open Package Manager",
                duration_seconds=time_module.time() - start_time,
                steps_completed=1,
                steps_total=total_steps,
                errors=errors
            )

        time_module.sleep(1.0)  # Wait for Package Manager to open

        if self._is_cancelled():
            return self._cancelled_result("install_meta_xr_sdk", start_time, 2, total_steps)

        # Step 3: Install from Asset Store
        self._report_progress(
            progress_callback, WorkflowStep.INSTALL_META_SDK, WorkflowStatus.IN_PROGRESS,
            f"Installing {pkg_name}...", 40, 3, total_steps
        )

        success, message = self._agent.install_package_from_asset_store(pkg_name)

        if not success:
            # Try alternate package names
            for alt_name in self.META_XR_SDK_PACKAGE_ALT_NAMES:
                if alt_name == pkg_name:
                    continue
                success, message = self._agent.install_package_from_asset_store(alt_name)
                if success:
                    pkg_name = alt_name
                    break

        if not success:
            errors.append(f"Failed to install package: {message}")
            return WorkflowResult(
                success=False,
                workflow_name="install_meta_xr_sdk",
                message=f"Failed to install {pkg_name}: {message}",
                duration_seconds=time_module.time() - start_time,
                steps_completed=2,
                steps_total=total_steps,
                errors=errors
            )

        if self._is_cancelled():
            return self._cancelled_result("install_meta_xr_sdk", start_time, 3, total_steps)

        # Step 4: Handle dialogs
        self._report_progress(
            progress_callback, WorkflowStep.HANDLE_DIALOGS, WorkflowStatus.IN_PROGRESS,
            "Handling import dialogs...", 60, 4, total_steps
        )

        self._agent.handle_all_dialogs(max_dialogs=5, timeout=30.0)
        time_module.sleep(1.0)

        if self._is_cancelled():
            return self._cancelled_result("install_meta_xr_sdk", start_time, 4, total_steps)

        # Step 5: Wait for import
        self._report_progress(
            progress_callback, WorkflowStep.WAIT_FOR_IMPORT, WorkflowStatus.IN_PROGRESS,
            "Waiting for package import...", 80, 5, total_steps
        )

        import_success, import_msg = self._agent.wait_for_package_import(timeout=300.0)

        if not import_success:
            errors.append(f"Import timed out: {import_msg}")

        # Final progress report
        self._report_progress(
            progress_callback, WorkflowStep.COMPLETE, WorkflowStatus.COMPLETED,
            "Meta XR SDK installation complete", 100, total_steps, total_steps,
            details={"package_name": pkg_name}
        )

        return WorkflowResult(
            success=True,
            workflow_name="install_meta_xr_sdk",
            message=f"Successfully installed {pkg_name}",
            duration_seconds=time_module.time() - start_time,
            steps_completed=total_steps,
            steps_total=total_steps,
            errors=errors if errors else None,
            details={"package_name": pkg_name}
        )

    # =========================================================================
    # configure_xr_settings - Enable XR plugins and apply settings
    # =========================================================================

    def configure_xr_settings(
        self,
        platform: str = "Android",
        xr_plugin: str = "Oculus",
        progress_callback: ProgressCallback = None
    ) -> WorkflowResult:
        """
        Configure XR settings for Quest development.

        This workflow:
        1. Opens Project Settings
        2. Navigates to XR Plug-in Management
        3. Enables the specified XR plugin for the platform
        4. Waits for any recompilation

        Args:
            platform: Target platform (default: Android).
            xr_plugin: XR plugin to enable (default: Oculus).
            progress_callback: Optional callback for progress updates.

        Returns:
            WorkflowResult with success status and details.
        """
        import time as time_module
        start_time = time_module.time()
        self._reset_cancel()

        total_steps = 4
        errors: List[str] = []

        # Step 1: Check Unity is running
        self._report_progress(
            progress_callback, WorkflowStep.CHECK_UNITY, WorkflowStatus.IN_PROGRESS,
            "Checking Unity status...", 0, 1, total_steps
        )

        if not self._agent.is_unity_running():
            return WorkflowResult(
                success=False,
                workflow_name="configure_xr_settings",
                message="Unity is not running",
                duration_seconds=time_module.time() - start_time,
                steps_completed=0,
                steps_total=total_steps,
                errors=["Unity Editor must be running"]
            )

        if self._is_cancelled():
            return self._cancelled_result("configure_xr_settings", start_time, 1, total_steps)

        # Step 2: Open Project Settings
        self._report_progress(
            progress_callback, WorkflowStep.CONFIGURE_XR, WorkflowStatus.IN_PROGRESS,
            "Opening Project Settings...", 25, 2, total_steps
        )

        if not self._agent.open_project_settings():
            errors.append("Failed to open Project Settings")
            return WorkflowResult(
                success=False,
                workflow_name="configure_xr_settings",
                message="Failed to open Project Settings",
                duration_seconds=time_module.time() - start_time,
                steps_completed=1,
                steps_total=total_steps,
                errors=errors
            )

        time_module.sleep(0.5)

        if self._is_cancelled():
            return self._cancelled_result("configure_xr_settings", start_time, 2, total_steps)

        # Step 3: Enable XR plugin
        self._report_progress(
            progress_callback, WorkflowStep.CONFIGURE_XR, WorkflowStatus.IN_PROGRESS,
            f"Enabling {xr_plugin} for {platform}...", 50, 3, total_steps
        )

        success, message = self._agent.enable_xr_plugin(platform, xr_plugin)

        if not success:
            errors.append(f"Failed to enable XR plugin: {message}")
            return WorkflowResult(
                success=False,
                workflow_name="configure_xr_settings",
                message=f"Failed to enable {xr_plugin}: {message}",
                duration_seconds=time_module.time() - start_time,
                steps_completed=2,
                steps_total=total_steps,
                errors=errors
            )

        if self._is_cancelled():
            return self._cancelled_result("configure_xr_settings", start_time, 3, total_steps)

        # Step 4: Wait for recompilation
        self._report_progress(
            progress_callback, WorkflowStep.WAIT_FOR_RECOMPILE, WorkflowStatus.IN_PROGRESS,
            "Waiting for recompilation...", 75, 4, total_steps
        )

        recompile_success, recompile_msg = self._agent.wait_for_recompilation(timeout=60.0)

        if not recompile_success:
            errors.append(f"Recompilation wait: {recompile_msg}")

        # Get final XR plugins state
        enabled_plugins = self._agent.get_xr_plugins(platform)

        # Final progress report
        self._report_progress(
            progress_callback, WorkflowStep.COMPLETE, WorkflowStatus.COMPLETED,
            "XR settings configured", 100, total_steps, total_steps,
            details={"platform": platform, "plugin": xr_plugin, "enabled_plugins": enabled_plugins}
        )

        return WorkflowResult(
            success=True,
            workflow_name="configure_xr_settings",
            message=f"Successfully enabled {xr_plugin} for {platform}",
            duration_seconds=time_module.time() - start_time,
            steps_completed=total_steps,
            steps_total=total_steps,
            errors=errors if errors else None,
            details={
                "platform": platform,
                "plugin": xr_plugin,
                "enabled_plugins": enabled_plugins
            }
        )

    # =========================================================================
    # build_and_deploy_quest - Build and deploy to Quest device
    # =========================================================================

    def build_and_deploy_quest(
        self,
        output_path: Optional[str] = None,
        device_id: Optional[str] = None,
        development_build: bool = True,
        timeout: float = 600.0,
        progress_callback: ProgressCallback = None
    ) -> WorkflowResult:
        """
        Build an APK and deploy to a connected Quest device.

        This workflow:
        1. Ensures build target is Android
        2. Gets connected devices and validates Quest is connected
        3. Configures build options (development build, etc.)
        4. Builds the APK
        5. Deploys to the Quest device

        Args:
            output_path: Optional output path for APK. Auto-generates if not provided.
            device_id: Optional device ID. Uses first Quest if not specified.
            development_build: Whether to create a development build (default: True).
            timeout: Build timeout in seconds (default: 600).
            progress_callback: Optional callback for progress updates.

        Returns:
            WorkflowResult with success status and details.
        """
        import time as time_module
        import os
        start_time = time_module.time()
        self._reset_cancel()

        total_steps = 6
        errors: List[str] = []

        # Step 1: Check Unity is running
        self._report_progress(
            progress_callback, WorkflowStep.CHECK_UNITY, WorkflowStatus.IN_PROGRESS,
            "Checking Unity status...", 0, 1, total_steps
        )

        if not self._agent.is_unity_running():
            return WorkflowResult(
                success=False,
                workflow_name="build_and_deploy_quest",
                message="Unity is not running",
                duration_seconds=time_module.time() - start_time,
                steps_completed=0,
                steps_total=total_steps,
                errors=["Unity Editor must be running"]
            )

        if self._is_cancelled():
            return self._cancelled_result("build_and_deploy_quest", start_time, 1, total_steps)

        # Step 2: Get connected devices
        self._report_progress(
            progress_callback, WorkflowStep.DEPLOY_TO_DEVICE, WorkflowStatus.IN_PROGRESS,
            "Checking connected devices...", 10, 2, total_steps
        )

        devices = self._agent.get_connected_devices()
        quest_devices = [d for d in devices if d.is_quest]

        if not devices:
            return WorkflowResult(
                success=False,
                workflow_name="build_and_deploy_quest",
                message="No devices connected via ADB",
                duration_seconds=time_module.time() - start_time,
                steps_completed=1,
                steps_total=total_steps,
                errors=["Connect a Quest device via USB and enable USB debugging"]
            )

        if not quest_devices:
            errors.append("No Quest devices found, using first available device")
            target_device = devices[0]
        elif device_id:
            target_device = next(
                (d for d in quest_devices if d.device_id == device_id),
                quest_devices[0]
            )
        else:
            target_device = quest_devices[0]

        if self._is_cancelled():
            return self._cancelled_result("build_and_deploy_quest", start_time, 2, total_steps)

        # Step 3: Switch to Android platform if needed
        self._report_progress(
            progress_callback, WorkflowStep.BUILD_APK, WorkflowStatus.IN_PROGRESS,
            "Checking build platform...", 20, 3, total_steps
        )

        current_platform = self._agent.get_current_platform()
        if current_platform != BuildTargetPlatform.ANDROID:
            self._report_progress(
                progress_callback, WorkflowStep.BUILD_APK, WorkflowStatus.IN_PROGRESS,
                "Switching to Android platform...", 25, 3, total_steps
            )

            success, message = self._agent.switch_platform("Android")
            if not success:
                errors.append(f"Platform switch failed: {message}")
                return WorkflowResult(
                    success=False,
                    workflow_name="build_and_deploy_quest",
                    message="Failed to switch to Android platform",
                    duration_seconds=time_module.time() - start_time,
                    steps_completed=2,
                    steps_total=total_steps,
                    errors=errors
                )

        if self._is_cancelled():
            return self._cancelled_result("build_and_deploy_quest", start_time, 3, total_steps)

        # Step 4: Configure build options
        self._report_progress(
            progress_callback, WorkflowStep.BUILD_APK, WorkflowStatus.IN_PROGRESS,
            "Configuring build options...", 35, 4, total_steps
        )

        build_options = BuildOptions(
            development_build=development_build,
            autoconnect_profiler=development_build,
            script_debugging=development_build,
            scripting_backend=BuildScriptingBackend.IL2CPP
        )

        success, message = self._agent.set_build_options(build_options)
        if not success:
            errors.append(f"Build options: {message}")

        if self._is_cancelled():
            return self._cancelled_result("build_and_deploy_quest", start_time, 4, total_steps)

        # Step 5: Build APK
        self._report_progress(
            progress_callback, WorkflowStep.BUILD_APK, WorkflowStatus.IN_PROGRESS,
            "Building APK...", 50, 5, total_steps
        )

        # Generate output path if not provided
        if not output_path:
            project = self._agent.get_open_project()
            project_name = project.name if project else "Build"
            timestamp = time_module.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                f"{project_name}_{timestamp}.apk"
            )

        build_result = self._agent.build_and_run(
            device=target_device.device_id,
            timeout=timeout
        )

        if build_result.result != BuildResult.SUCCESS:
            error_msgs = [e.message for e in (build_result.errors or [])]
            errors.extend(error_msgs)
            return WorkflowResult(
                success=False,
                workflow_name="build_and_deploy_quest",
                message=f"Build failed: {build_result.message}",
                duration_seconds=time_module.time() - start_time,
                steps_completed=4,
                steps_total=total_steps,
                errors=errors,
                details={
                    "build_result": build_result.result.value,
                    "build_errors": error_msgs
                }
            )

        if self._is_cancelled():
            return self._cancelled_result("build_and_deploy_quest", start_time, 5, total_steps)

        # Step 6: Verify deployment
        self._report_progress(
            progress_callback, WorkflowStep.DEPLOY_TO_DEVICE, WorkflowStatus.IN_PROGRESS,
            f"Deployed to {target_device.model}", 90, 6, total_steps
        )

        time_module.sleep(2.0)  # Allow deployment to complete

        # Final progress report
        self._report_progress(
            progress_callback, WorkflowStep.COMPLETE, WorkflowStatus.COMPLETED,
            "Build and deploy complete", 100, total_steps, total_steps,
            details={
                "device": target_device.device_id,
                "model": target_device.model,
                "output_path": output_path,
                "build_time": build_result.build_time_seconds
            }
        )

        return WorkflowResult(
            success=True,
            workflow_name="build_and_deploy_quest",
            message=f"Successfully built and deployed to {target_device.model}",
            duration_seconds=time_module.time() - start_time,
            steps_completed=total_steps,
            steps_total=total_steps,
            errors=errors if errors else None,
            details={
                "device_id": target_device.device_id,
                "device_model": target_device.model,
                "output_path": output_path,
                "build_time_seconds": build_result.build_time_seconds,
                "development_build": development_build
            }
        )

    # =========================================================================
    # setup_quest3_project - Full Quest 3 SDK setup workflow
    # =========================================================================

    def setup_quest3_project(
        self,
        install_sdk: bool = True,
        configure_xr: bool = True,
        run_meta_setup: bool = True,
        add_define_symbol: bool = True,
        progress_callback: ProgressCallback = None
    ) -> WorkflowResult:
        """
        Complete Quest 3 project setup workflow.

        This is the main workflow that combines all setup steps:
        1. Installs Meta XR SDK from Asset Store (if install_sdk=True)
        2. Enables XR Plug-in Management with Oculus plugin (if configure_xr=True)
        3. Runs Meta Project Setup Tool Fix All and Apply All (if run_meta_setup=True)
        4. Adds OCULUS_XR_SDK scripting define symbol (if add_define_symbol=True)
        5. Waits for all imports and recompilation

        Each sub-step can be disabled if already completed or not needed.

        Args:
            install_sdk: Whether to install Meta XR SDK (default: True).
            configure_xr: Whether to configure XR settings (default: True).
            run_meta_setup: Whether to run Meta Setup Tool (default: True).
            add_define_symbol: Whether to add OCULUS_XR_SDK symbol (default: True).
            progress_callback: Optional callback for progress updates.

        Returns:
            WorkflowResult with success status and details.
        """
        import time as time_module
        start_time = time_module.time()
        self._reset_cancel()

        # Calculate total steps based on enabled options
        total_steps = 1  # Unity check
        if install_sdk:
            total_steps += 3  # SDK install, dialogs, import wait
        if configure_xr:
            total_steps += 2  # XR config, recompile wait
        if run_meta_setup:
            total_steps += 2  # Meta setup, wait
        if add_define_symbol:
            total_steps += 2  # Symbol add, recompile wait
        total_steps += 1  # Final check

        current_step = 0
        errors: List[str] = []
        details: dict = {
            "install_sdk": install_sdk,
            "configure_xr": configure_xr,
            "run_meta_setup": run_meta_setup,
            "add_define_symbol": add_define_symbol
        }

        # Step: Check Unity is running
        current_step += 1
        self._report_progress(
            progress_callback, WorkflowStep.CHECK_UNITY, WorkflowStatus.IN_PROGRESS,
            "Checking Unity status...", (current_step / total_steps) * 100,
            current_step, total_steps
        )

        if not self._agent.is_unity_running():
            return WorkflowResult(
                success=False,
                workflow_name="setup_quest3_project",
                message="Unity is not running",
                duration_seconds=time_module.time() - start_time,
                steps_completed=0,
                steps_total=total_steps,
                errors=["Unity Editor must be running with a project open"]
            )

        project = self._agent.get_open_project()
        if project:
            details["project_name"] = project.name
            details["project_path"] = project.path
            details["unity_version"] = project.version

        if self._is_cancelled():
            return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

        # =====================================================================
        # SDK Installation
        # =====================================================================
        if install_sdk:
            # Check if SDK is already installed
            if self._agent.is_meta_sdk_installed():
                self._report_progress(
                    progress_callback, WorkflowStep.INSTALL_META_SDK, WorkflowStatus.IN_PROGRESS,
                    "Meta XR SDK already installed, skipping...",
                    (current_step / total_steps) * 100, current_step, total_steps
                )
                details["sdk_status"] = "already_installed"
                current_step += 3  # Skip SDK-related steps
            else:
                # Install SDK
                current_step += 1
                self._report_progress(
                    progress_callback, WorkflowStep.INSTALL_META_SDK, WorkflowStatus.IN_PROGRESS,
                    "Installing Meta XR SDK...",
                    (current_step / total_steps) * 100, current_step, total_steps
                )

                if not self._agent.open_package_manager():
                    errors.append("Failed to open Package Manager")

                time_module.sleep(1.0)

                if self._is_cancelled():
                    return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

                success, msg = self._agent.install_package_from_asset_store(
                    self.META_XR_SDK_PACKAGE_NAME
                )

                if not success:
                    # Try alternate names
                    for alt_name in self.META_XR_SDK_PACKAGE_ALT_NAMES:
                        success, msg = self._agent.install_package_from_asset_store(alt_name)
                        if success:
                            break

                if not success:
                    errors.append(f"SDK installation: {msg}")
                    # Continue anyway - SDK might need to be installed manually

                # Handle dialogs
                current_step += 1
                self._report_progress(
                    progress_callback, WorkflowStep.HANDLE_DIALOGS, WorkflowStatus.IN_PROGRESS,
                    "Handling import dialogs...",
                    (current_step / total_steps) * 100, current_step, total_steps
                )

                dialog_results = self._agent.handle_all_dialogs(max_dialogs=5, timeout=30.0)
                details["dialogs_handled"] = len([r for r in dialog_results if r.handled])

                if self._is_cancelled():
                    return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

                # Wait for import
                current_step += 1
                self._report_progress(
                    progress_callback, WorkflowStep.WAIT_FOR_IMPORT, WorkflowStatus.IN_PROGRESS,
                    "Waiting for SDK import...",
                    (current_step / total_steps) * 100, current_step, total_steps
                )

                import_success, import_msg = self._agent.wait_for_package_import(timeout=300.0)
                if not import_success:
                    errors.append(f"SDK import: {import_msg}")

                details["sdk_status"] = "installed" if success else "failed"

        if self._is_cancelled():
            return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

        # =====================================================================
        # XR Configuration
        # =====================================================================
        if configure_xr:
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.CONFIGURE_XR, WorkflowStatus.IN_PROGRESS,
                "Configuring XR settings...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            if not self._agent.open_project_settings():
                errors.append("Failed to open Project Settings")

            time_module.sleep(0.5)

            success, msg = self._agent.enable_xr_plugin("Android", "Oculus")
            if not success:
                errors.append(f"XR plugin enable: {msg}")
            else:
                details["xr_plugin_enabled"] = "Oculus"

            if self._is_cancelled():
                return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

            # Wait for recompilation
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.WAIT_FOR_RECOMPILE, WorkflowStatus.IN_PROGRESS,
                "Waiting for recompilation...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            recompile_success, _ = self._agent.wait_for_recompilation(timeout=60.0)
            if not recompile_success:
                errors.append("Recompilation timeout after XR config")

        if self._is_cancelled():
            return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

        # =====================================================================
        # Meta Project Setup Tool
        # =====================================================================
        if run_meta_setup:
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.RUN_META_SETUP, WorkflowStatus.IN_PROGRESS,
                "Running Meta Project Setup Tool...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            setup_result, msg = self._agent.open_meta_setup_tool()
            if not setup_result:
                errors.append(f"Meta setup tool: {msg}")
            else:
                time_module.sleep(1.0)

                # Run Fix All
                fix_result = self._agent.run_fix_all()
                details["meta_setup_fixed"] = len(fix_result.fixed_issues)
                details["meta_setup_remaining"] = len(fix_result.remaining_issues)

                if not fix_result.success:
                    errors.append(f"Meta Fix All: {fix_result.message}")

                time_module.sleep(0.5)

                # Run Apply All
                apply_result = self._agent.run_apply_all()
                if not apply_result.success:
                    errors.append(f"Meta Apply All: {apply_result.message}")

            if self._is_cancelled():
                return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

            # Wait for setup completion
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.RUN_META_SETUP, WorkflowStatus.IN_PROGRESS,
                "Waiting for Meta setup to complete...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            setup_wait_success, _ = self._agent.wait_for_setup_complete(timeout=60.0)
            if not setup_wait_success:
                errors.append("Meta setup wait timeout")

            # Handle any dialogs from setup
            self._agent.handle_all_dialogs(max_dialogs=3, timeout=10.0)

        if self._is_cancelled():
            return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

        # =====================================================================
        # Scripting Define Symbol
        # =====================================================================
        if add_define_symbol:
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.ADD_DEFINE_SYMBOLS, WorkflowStatus.IN_PROGRESS,
                f"Adding {self.QUEST_DEFINE_SYMBOL} symbol...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            # Check if symbol already exists
            current_symbols = self._agent.get_define_symbols("Android")
            if self.QUEST_DEFINE_SYMBOL in current_symbols:
                details["define_symbol_status"] = "already_present"
            else:
                success, new_symbols = self._agent.add_define_symbol(
                    "Android", self.QUEST_DEFINE_SYMBOL
                )
                if not success:
                    errors.append(f"Add define symbol failed")
                else:
                    details["define_symbol_status"] = "added"
                    details["current_symbols"] = new_symbols

            if self._is_cancelled():
                return self._cancelled_result("setup_quest3_project", start_time, current_step, total_steps)

            # Wait for recompilation
            current_step += 1
            self._report_progress(
                progress_callback, WorkflowStep.WAIT_FOR_RECOMPILE, WorkflowStatus.IN_PROGRESS,
                "Waiting for final recompilation...",
                (current_step / total_steps) * 100, current_step, total_steps
            )

            recompile_success, _ = self._agent.wait_for_recompilation(timeout=60.0)
            if not recompile_success:
                errors.append("Final recompilation timeout")

        # =====================================================================
        # Final Check
        # =====================================================================
        current_step += 1
        self._report_progress(
            progress_callback, WorkflowStep.COMPLETE, WorkflowStatus.IN_PROGRESS,
            "Performing final checks...",
            (current_step / total_steps) * 100, current_step, total_steps
        )

        # Wait for Unity to be fully idle
        idle_success, _ = self._agent.wait_for_idle(timeout=30.0)
        if not idle_success:
            errors.append("Unity did not reach idle state")

        # Check for console errors
        if self._agent.has_console_errors():
            console_errors = self._agent.get_console_messages(
                level=ConsoleMessageLevel.ERROR,
                max_messages=5
            )
            error_texts = [e.message[:100] for e in console_errors]
            errors.extend(error_texts)
            details["console_errors"] = len(console_errors)

        # Final status
        success = len([e for e in errors if "Failed" in e or "error" in e.lower()]) == 0

        self._report_progress(
            progress_callback, WorkflowStep.COMPLETE, WorkflowStatus.COMPLETED,
            "Quest 3 project setup complete" if success else "Setup completed with issues",
            100, total_steps, total_steps,
            details=details
        )

        return WorkflowResult(
            success=success,
            workflow_name="setup_quest3_project",
            message="Quest 3 project setup complete" if success else "Setup completed with errors",
            duration_seconds=time_module.time() - start_time,
            steps_completed=current_step,
            steps_total=total_steps,
            errors=errors if errors else None,
            details=details
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _cancelled_result(
        self,
        workflow_name: str,
        start_time: float,
        steps_completed: int,
        total_steps: int
    ) -> WorkflowResult:
        """Create a cancelled workflow result."""
        import time as time_module
        return WorkflowResult(
            success=False,
            workflow_name=workflow_name,
            message="Workflow cancelled",
            duration_seconds=time_module.time() - start_time,
            steps_completed=steps_completed,
            steps_total=total_steps,
            errors=["Workflow was cancelled by user"]
        )


# Convenience function for quick checks
def is_unity_available() -> bool:
    """
    Quick check if Unity is running and ready for automation.

    Returns:
        True if Unity is running and accessible.
    """
    return UnityAgent().is_unity_running()


def get_unity_project() -> Optional[UnityProject]:
    """
    Get information about the currently open Unity project.

    Returns:
        UnityProject if available, None otherwise.
    """
    return UnityAgent().get_open_project()
