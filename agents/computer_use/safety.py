#!/usr/bin/env python3
"""
safety.py - Unity Dialog Safety Patterns

This module defines safe dialog handling patterns for Unity Editor automation.
It provides predefined configurations for common Unity dialogs to ensure
automated workflows handle prompts safely and predictably.

Usage:
    from agents.computer_use.safety import (
        UNITY_DIALOG_PATTERNS,
        get_safe_dialog_config,
        apply_safe_defaults,
    )
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# =============================================================================
# Dialog Pattern Definitions
# =============================================================================


@dataclass
class DialogPattern:
    """Pattern for detecting and handling a Unity dialog.

    Attributes:
        name: Human-readable name for this dialog type.
        window_title_contains: List of substrings that identify this dialog by window title.
        button_accept: Button name(s) to click when accepting.
        button_reject: Button name(s) to click when rejecting.
        button_dismiss: Button name(s) to click when dismissing.
        is_blocking: Whether this dialog blocks Unity operations.
        requires_wait: Whether to wait after handling (e.g., editor restart).
        wait_seconds: How long to wait after handling.
        auto_handle: Whether this dialog should be auto-handled by default.
        description: Description of what this dialog means.
    """
    name: str
    window_title_contains: List[str]
    button_accept: List[str] = field(default_factory=lambda: ["Yes", "OK"])
    button_reject: List[str] = field(default_factory=lambda: ["No", "Cancel"])
    button_dismiss: List[str] = field(default_factory=lambda: ["Close", "X"])
    is_blocking: bool = True
    requires_wait: bool = False
    wait_seconds: float = 1.0
    auto_handle: bool = True
    description: str = ""


# =============================================================================
# Unity Dialog Patterns
# =============================================================================


UNITY_DIALOG_PATTERNS: Dict[str, DialogPattern] = {
    # Input System dialog - appears when changing input handling settings
    "input_system": DialogPattern(
        name="Enable New Input System",
        window_title_contains=["Input System", "Input Manager"],
        button_accept=["Yes"],
        button_reject=["No"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=2.0,
        auto_handle=True,
        description="Prompts to enable the new Input System package, requires editor restart"
    ),

    # API Update dialog - appears when APIs need updating after Unity upgrade
    "api_update": DialogPattern(
        name="API Update Required",
        window_title_contains=["API Update"],
        button_accept=["I Made a Backup. Go Ahead!", "Update"],
        button_reject=["Don't Update", "Cancel"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=5.0,
        auto_handle=True,
        description="Prompts to update deprecated APIs after Unity version upgrade"
    ),

    # Restart Editor dialog - various operations require editor restart
    "restart_editor": DialogPattern(
        name="Restart Editor",
        window_title_contains=["Restart"],
        button_accept=["Yes", "Restart", "OK"],
        button_reject=["No", "Cancel", "Later"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=5.0,
        auto_handle=True,
        description="Prompts to restart Unity Editor to apply changes"
    ),

    # Safe Mode dialog - appears when scripts have compilation errors
    "safe_mode": DialogPattern(
        name="Enter Safe Mode",
        window_title_contains=["Safe Mode"],
        button_accept=["Enter Safe Mode"],
        button_reject=["Ignore", "Continue"],
        is_blocking=True,
        requires_wait=False,
        wait_seconds=1.0,
        auto_handle=False,  # Default: don't auto-enter safe mode
        description="Prompts to enter Safe Mode when compilation errors exist"
    ),

    # Build Failed dialog - appears after a failed build
    "build_failed": DialogPattern(
        name="Build Failed",
        window_title_contains=["Build", "Failed", "Error"],
        button_accept=[],
        button_reject=[],
        button_dismiss=["OK", "Close"],
        is_blocking=True,
        requires_wait=False,
        wait_seconds=0.5,
        auto_handle=True,
        description="Shows build failure information, needs dismissal"
    ),

    # Import dialog - appears when importing packages
    "import": DialogPattern(
        name="Import Package",
        window_title_contains=["Import"],
        button_accept=["Import", "Import All", "OK"],
        button_reject=["Cancel"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=2.0,
        auto_handle=True,
        description="Prompts to confirm package import"
    ),

    # Save Scene dialog - appears when leaving unsaved scene
    "save_scene": DialogPattern(
        name="Save Scene",
        window_title_contains=["Save", "Scene"],
        button_accept=["Save", "Yes"],
        button_reject=["Don't Save", "No"],
        button_dismiss=["Cancel"],
        is_blocking=True,
        requires_wait=False,
        wait_seconds=1.0,
        auto_handle=True,
        description="Prompts to save current scene before proceeding"
    ),

    # Script Reload dialog
    "script_reload": DialogPattern(
        name="Script Reload",
        window_title_contains=["Script", "Reload"],
        button_accept=["Yes", "Reload", "OK"],
        button_reject=["No", "Cancel"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=2.0,
        auto_handle=True,
        description="Prompts to reload scripts after external changes"
    ),

    # Asset Import Overwrite dialog
    "asset_overwrite": DialogPattern(
        name="Asset Overwrite",
        window_title_contains=["Overwrite", "Replace"],
        button_accept=["Yes", "Replace", "Overwrite", "OK"],
        button_reject=["No", "Keep", "Cancel"],
        is_blocking=True,
        requires_wait=False,
        wait_seconds=0.5,
        auto_handle=True,
        description="Prompts to confirm overwriting existing assets"
    ),

    # XR Plugin dialog - appears when enabling/disabling XR plugins
    "xr_plugin": DialogPattern(
        name="XR Plugin Change",
        window_title_contains=["XR", "Plugin"],
        button_accept=["Yes", "Enable", "OK"],
        button_reject=["No", "Cancel"],
        is_blocking=True,
        requires_wait=True,
        wait_seconds=3.0,
        auto_handle=True,
        description="Prompts related to XR plugin changes"
    ),

    # Android SDK dialog - appears when SDK paths aren't configured
    "android_sdk": DialogPattern(
        name="Android SDK Required",
        window_title_contains=["Android", "SDK"],
        button_accept=["OK", "Continue"],
        button_reject=["Cancel"],
        is_blocking=True,
        requires_wait=False,
        wait_seconds=0.5,
        auto_handle=False,  # User should configure SDK manually
        description="Prompts about Android SDK configuration"
    ),
}


# =============================================================================
# Safety Helper Functions
# =============================================================================


def get_pattern(dialog_key: str) -> Optional[DialogPattern]:
    """
    Get a dialog pattern by its key.

    Args:
        dialog_key: Key from UNITY_DIALOG_PATTERNS.

    Returns:
        DialogPattern if found, None otherwise.
    """
    return UNITY_DIALOG_PATTERNS.get(dialog_key)


def get_patterns_for_window_title(window_title: str) -> List[DialogPattern]:
    """
    Find all dialog patterns that match a window title.

    Args:
        window_title: The window title to match against.

    Returns:
        List of matching DialogPattern objects.
    """
    matches = []
    window_title_lower = window_title.lower()
    for pattern in UNITY_DIALOG_PATTERNS.values():
        for substring in pattern.window_title_contains:
            if substring.lower() in window_title_lower:
                matches.append(pattern)
                break
    return matches


def get_auto_handle_patterns() -> Dict[str, DialogPattern]:
    """
    Get all patterns configured for automatic handling.

    Returns:
        Dictionary of dialog patterns with auto_handle=True.
    """
    return {
        key: pattern
        for key, pattern in UNITY_DIALOG_PATTERNS.items()
        if pattern.auto_handle
    }


def get_blocking_patterns() -> Dict[str, DialogPattern]:
    """
    Get all patterns that represent blocking dialogs.

    Returns:
        Dictionary of dialog patterns with is_blocking=True.
    """
    return {
        key: pattern
        for key, pattern in UNITY_DIALOG_PATTERNS.items()
        if pattern.is_blocking
    }


def create_custom_pattern(
    name: str,
    window_title_contains: List[str],
    accept_buttons: Optional[List[str]] = None,
    reject_buttons: Optional[List[str]] = None,
    auto_handle: bool = True,
    wait_seconds: float = 1.0
) -> DialogPattern:
    """
    Create a custom dialog pattern.

    Args:
        name: Human-readable name for the pattern.
        window_title_contains: Substrings to identify this dialog.
        accept_buttons: Button names to click when accepting.
        reject_buttons: Button names to click when rejecting.
        auto_handle: Whether to auto-handle this dialog.
        wait_seconds: Time to wait after handling.

    Returns:
        A new DialogPattern instance.

    Example:
        custom = create_custom_pattern(
            name="My Custom Dialog",
            window_title_contains=["Custom", "Dialog"],
            accept_buttons=["Proceed"],
            auto_handle=True
        )
    """
    return DialogPattern(
        name=name,
        window_title_contains=window_title_contains,
        button_accept=accept_buttons or ["Yes", "OK"],
        button_reject=reject_buttons or ["No", "Cancel"],
        auto_handle=auto_handle,
        wait_seconds=wait_seconds
    )


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "DialogPattern",
    "UNITY_DIALOG_PATTERNS",
    "get_pattern",
    "get_patterns_for_window_title",
    "get_auto_handle_patterns",
    "get_blocking_patterns",
    "create_custom_pattern",
]
