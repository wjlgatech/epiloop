"""
computer_use - Computer automation agents for macOS.

This package provides automation capabilities for various applications
on macOS, using AppleScript and system-level controls.

Modules:
    unity: Unity Editor automation for XR/Quest development
    safety: Dialog safety patterns for Unity automation
    screenshot: Multi-monitor screenshot capture with coordinate mapping
    unity_monitor: Unity Editor.log monitoring for build progress tracking
    vision_finder: Vision-based UI element detection using Claude API
    click_helper: Click operations with vision-based fallback
    dialog_registry: YAML-configurable dialog handler registry
"""

from .unity import (
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
    # Build automation
    BuildTargetPlatform,
    BuildScriptingBackend,
    BuildResult,
    BuildOptions,
    BuildError,
    BuildResultInfo,
    ConnectedDevice,
    # State detection
    ConsoleMessageLevel,
    ConsoleMessage,
    EditorState,
    # Dialog handling
    DialogType,
    DialogAction,
    DialogConfig,
    DialogHandleResult,
    DialogLog,
    # Workflow orchestration
    WorkflowStep,
    WorkflowStatus,
    WorkflowProgress,
    WorkflowResult,
    UnityWorkflows,
    # Vision-based automation (GUI-009)
    VisionWorkflowStatus,
    VisionWorkflowResult,
    PanelStateResult,
    BuildProgressInfo,
    # Convenience functions
    is_unity_available,
    get_unity_project,
)

from .safety import (
    DialogPattern,
    UNITY_DIALOG_PATTERNS,
    get_pattern,
    get_patterns_for_window_title,
    get_auto_handle_patterns,
    get_blocking_patterns,
    create_custom_pattern,
)

from .orchestrator import (
    UnityOrchestrator,
    UnityCommandRegistry,
    WorkflowExecutor,
    CommandStatus,
    CommandResult,
    WorkflowStepDefinition,
    WorkflowDefinition,
    WorkflowExecutionResult,
)

from .run_quest3_workflow import (
    Quest3WorkflowExecutor,
    AcceptanceCriterion,
    CriteriaStatus,
    WorkflowExecutionReport,
)

# Screenshot capture - may not be available if Quartz/PIL not installed
try:
    from .screenshot import (
        MultiMonitorCapture,
        DisplayInfo,
        DisplayBounds,
        DisplayArrangement,
        CombinedDisplaySpace,
        ScreenshotResult,
        WindowInfo,
        DEFAULT_SCREENSHOT_DIR,
        # Convenience functions
        capture_screenshot,
        get_display_info,
        get_display_list,
        coordinate_to_display,
        display_to_global,
        get_windows,
        capture_window,
        get_window_display,
        save_screenshot_with_timestamp,
    )
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False

# Unity log monitoring - always available (standard library only)
try:
    from .unity_monitor import (
        UnityLogMonitor,
        BuildEventType,
        BuildPhase,
        BuildEvent,
        BuildErrorInfo,
        BuildMonitorResult,
        # Convenience functions
        get_unity_log_path,
        monitor_unity_build,
        get_recent_unity_errors,
    )
    LOG_MONITOR_AVAILABLE = True
except ImportError:
    LOG_MONITOR_AVAILABLE = False

# Dialog registry availability flag (re-exported from dialog_registry)
try:
    from .dialog_registry import YAML_AVAILABLE
    DIALOG_REGISTRY_AVAILABLE = YAML_AVAILABLE
except ImportError:
    DIALOG_REGISTRY_AVAILABLE = False

# Checkpoint availability flag - always available (standard library only)
CHECKPOINT_AVAILABLE = True

# Vision-based element detection - may not be available if anthropic not installed
try:
    from .vision_finder import (
        VisionElementFinder,
        ElementLocation,
        APIUsageRecord,
        APIUsageStats,
        # Convenience functions
        find_element,
        find_element_with_retry,
    )
    VISION_FINDER_AVAILABLE = True
except ImportError:
    VISION_FINDER_AVAILABLE = False

# Vision detector (wrapper around vision_finder with additional convenience methods)
try:
    from .vision_detector import (
        VisionDetector,
        DetectionResult,
        BoundingBox,
        # Element state detection classes and enums
        ElementState,
        ButtonState,
        CheckboxState,
        ProgressState,
        # Element detection convenience functions
        find_element as vision_find_element,  # Aliased to avoid conflict
        find_button,
        find_all_buttons,
        # State detection convenience functions
        get_element_state,
        get_button_state,
        get_checkbox_state,
        get_text_field_content,
        get_dropdown_selection,
        get_error_message,
        get_status_text,
        get_progress_indicator,
        VISION_DETECTOR_AVAILABLE,
    )
except ImportError:
    VISION_DETECTOR_AVAILABLE = False

# Click helper with vision fallback - may not be available if Quartz not installed
try:
    from .click_helper import (
        ClickHelper,
        ClickMethod,
        ClickResult,
        # Convenience function
        click_with_vision_fallback,
    )
    CLICK_HELPER_AVAILABLE = True
except ImportError:
    CLICK_HELPER_AVAILABLE = False

# Mouse controller for coordinate-based clicking - may not be available if Quartz not installed
try:
    from .mouse_controller import (
        MouseController,
        MouseButton,
        ClickType,
        ClickResult as MouseClickResult,
        DragResult,
        ClickLogEntry,
        # Convenience functions
        click_at,
        double_click_at,
        right_click_at,
        drag_from_to,
        get_mouse_position,
        move_mouse_to,
    )
    MOUSE_CONTROLLER_AVAILABLE = True
except ImportError:
    MOUSE_CONTROLLER_AVAILABLE = False

# Unified click handler with fallback chain - integrates vision_detector + mouse_controller
try:
    from .click_handler import (
        ClickHandler,
        ClickHandlerResult,
        ClickMethod as HandlerClickMethod,
        FallbackReason,
        ElementBounds,
        # Convenience functions
        click_element,
        click_element_vision_only,
        CLICK_HANDLER_AVAILABLE,
    )
except ImportError:
    CLICK_HANDLER_AVAILABLE = False

# Unity panel detection - vision-based panel interaction for Unity Editor
try:
    from .unity_panels import (
        UnityPanelDetector,
        PanelType,
        PanelLayout,
        PanelBounds,
        PanelDetectionResult,
        ButtonInPanelResult,
        ClickInPanelResult,
        # Convenience functions
        is_panel_open,
        get_panel_bounds,
        wait_for_panel,
        click_button_in_panel,
        UNITY_PANELS_AVAILABLE,
    )
except ImportError:
    UNITY_PANELS_AVAILABLE = False

# Action logger for GUI automation debugging
try:
    from .action_logger import (
        ActionLogger,
        ActionLogEntry,
        SessionInfo,
        ActionType,
        ActionStatus,
        # Convenience functions
        create_action_logger,
        get_latest_session_report,
        list_all_sessions,
        cleanup_sessions,
        DEFAULT_SCREENSHOTS_BASE,
        ACTION_LOGGER_AVAILABLE,
    )
except ImportError:
    ACTION_LOGGER_AVAILABLE = False

# Wait utilities for UI state polling (GUI-008)
try:
    from .wait_utils import (
        WaitHelper,
        WaitResult,
        WaitProgress,
        WaitOutcome,
        PredicateFunc,
        # Convenience functions
        wait_for_element,
        wait_for_element_gone,
        wait_for_text,
        wait_for_button_enabled,
        wait_for_condition,
        wait_for_any_element,
        create_wait_helper,
        WAIT_UTILS_AVAILABLE,
    )
except ImportError:
    WAIT_UTILS_AVAILABLE = False

# Dialog registry - YAML-configurable dialog handlers
from .dialog_registry import (
    DialogRegistry,
    DialogHandler,
    DialogActionType,
    DialogMatchType,
    DialogMatchResult,
    DialogActionResult,
    DialogLogEntry,
    # Convenience functions
    load_dialog_registry,
    create_default_config,
    YAML_AVAILABLE,
)

# Workflow checkpointing
from .checkpoint import (
    WorkflowCheckpoint,
    CheckpointData,
    CheckpointInfo,
    # Convenience functions
    list_checkpoints,
    load_latest_checkpoint,
    cleanup_checkpoints,
    get_checkpoint_summary,
    DEFAULT_CHECKPOINT_DIR,
)

__all__ = [
    # Main agent class
    "UnityAgent",
    # Enums
    "UnityWindow",
    "UnityMenu",
    "PackageStatus",
    "PackageSource",
    "ProjectSettingsCategory",
    "Platform",
    "XRPlugin",
    "MetaSetupIssueLevel",
    "MetaSetupIssueStatus",
    "BuildTargetPlatform",
    "BuildScriptingBackend",
    "BuildResult",
    "ConsoleMessageLevel",
    "DialogType",
    "DialogAction",
    "WorkflowStep",
    "WorkflowStatus",
    # Data classes
    "UnityProject",
    "UnityState",
    "PackageInfo",
    "MetaSetupIssue",
    "MetaSetupResult",
    "BuildOptions",
    "BuildError",
    "BuildResultInfo",
    "ConnectedDevice",
    "ConsoleMessage",
    "EditorState",
    "DialogConfig",
    "DialogHandleResult",
    "DialogLog",
    "WorkflowProgress",
    "WorkflowResult",
    # Vision-based automation result types (GUI-009)
    "VisionWorkflowStatus",
    "VisionWorkflowResult",
    "PanelStateResult",
    "BuildProgressInfo",
    # Workflow orchestrator
    "UnityWorkflows",
    # Safety patterns
    "DialogPattern",
    "UNITY_DIALOG_PATTERNS",
    "get_pattern",
    "get_patterns_for_window_title",
    "get_auto_handle_patterns",
    "get_blocking_patterns",
    "create_custom_pattern",
    # Command orchestrator
    "UnityOrchestrator",
    "UnityCommandRegistry",
    "WorkflowExecutor",
    "CommandStatus",
    "CommandResult",
    "WorkflowStepDefinition",
    "WorkflowDefinition",
    "WorkflowExecutionResult",
    # Convenience functions
    "is_unity_available",
    "get_unity_project",
    # Quest 3 workflow execution
    "Quest3WorkflowExecutor",
    "AcceptanceCriterion",
    "CriteriaStatus",
    "WorkflowExecutionReport",
    # Screenshot capture (if available)
    "SCREENSHOT_AVAILABLE",
    "MultiMonitorCapture",
    "DisplayInfo",
    "DisplayBounds",
    "DisplayArrangement",
    "CombinedDisplaySpace",
    "ScreenshotResult",
    "WindowInfo",
    "DEFAULT_SCREENSHOT_DIR",
    "capture_screenshot",
    "get_display_info",
    "get_display_list",
    "coordinate_to_display",
    "display_to_global",
    "get_windows",
    "capture_window",
    "get_window_display",
    "save_screenshot_with_timestamp",
    # Unity log monitoring
    "UnityLogMonitor",
    "BuildEventType",
    "BuildPhase",
    "BuildEvent",
    "BuildErrorInfo",
    "BuildMonitorResult",
    "get_unity_log_path",
    "monitor_unity_build",
    "get_recent_unity_errors",
    # Vision-based element detection (if available)
    "VISION_FINDER_AVAILABLE",
    "VisionElementFinder",
    "ElementLocation",
    "APIUsageRecord",
    "APIUsageStats",
    "find_element",
    "find_element_with_retry",
    # Vision detector (wrapper with convenience methods)
    "VISION_DETECTOR_AVAILABLE",
    "VisionDetector",
    "DetectionResult",
    "BoundingBox",
    "vision_find_element",
    "find_button",
    "find_all_buttons",
    # Element state detection (GUI-006)
    "ElementState",
    "ButtonState",
    "CheckboxState",
    "ProgressState",
    "get_element_state",
    "get_button_state",
    "get_checkbox_state",
    "get_text_field_content",
    "get_dropdown_selection",
    "get_error_message",
    "get_status_text",
    "get_progress_indicator",
    # Click helper with vision fallback (if available)
    "CLICK_HELPER_AVAILABLE",
    "ClickHelper",
    "ClickMethod",
    "ClickResult",
    "click_with_vision_fallback",
    # Mouse controller for coordinate-based clicking (if available)
    "MOUSE_CONTROLLER_AVAILABLE",
    "MouseController",
    "MouseButton",
    "ClickType",
    "MouseClickResult",
    "DragResult",
    "ClickLogEntry",
    "click_at",
    "double_click_at",
    "right_click_at",
    "drag_from_to",
    "get_mouse_position",
    "move_mouse_to",
    # Unified click handler with fallback chain (if available)
    "CLICK_HANDLER_AVAILABLE",
    "ClickHandler",
    "ClickHandlerResult",
    "HandlerClickMethod",
    "FallbackReason",
    "ElementBounds",
    "click_element",
    "click_element_vision_only",
    # Unity panel detection (if available)
    "UNITY_PANELS_AVAILABLE",
    "UnityPanelDetector",
    "PanelType",
    "PanelLayout",
    "PanelBounds",
    "PanelDetectionResult",
    "ButtonInPanelResult",
    "ClickInPanelResult",
    "is_panel_open",
    "get_panel_bounds",
    "wait_for_panel",
    "click_button_in_panel",
    # Dialog registry (YAML-configurable dialog handlers)
    "DialogRegistry",
    "DialogHandler",
    "DialogActionType",
    "DialogMatchType",
    "DialogMatchResult",
    "DialogActionResult",
    "DialogLogEntry",
    "load_dialog_registry",
    "create_default_config",
    "YAML_AVAILABLE",
    # Workflow checkpointing
    "WorkflowCheckpoint",
    "CheckpointData",
    "CheckpointInfo",
    "list_checkpoints",
    "load_latest_checkpoint",
    "cleanup_checkpoints",
    "get_checkpoint_summary",
    "DEFAULT_CHECKPOINT_DIR",
    # Action logger (GUI-007)
    "ACTION_LOGGER_AVAILABLE",
    "ActionLogger",
    "ActionLogEntry",
    "SessionInfo",
    "ActionType",
    "ActionStatus",
    "create_action_logger",
    "get_latest_session_report",
    "list_all_sessions",
    "cleanup_sessions",
    "DEFAULT_SCREENSHOTS_BASE",
    # Wait utilities (GUI-008)
    "WAIT_UTILS_AVAILABLE",
    "WaitHelper",
    "WaitResult",
    "WaitProgress",
    "WaitOutcome",
    "PredicateFunc",
    "wait_for_element",
    "wait_for_element_gone",
    "wait_for_text",
    "wait_for_button_enabled",
    "wait_for_condition",
    "wait_for_any_element",
    "create_wait_helper",
    # Feature availability flags
    "LOG_MONITOR_AVAILABLE",
    "DIALOG_REGISTRY_AVAILABLE",
    "CHECKPOINT_AVAILABLE",
]
