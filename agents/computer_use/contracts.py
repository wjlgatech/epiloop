"""
Core contracts for the computer-use module.

This module defines the fundamental data types used across all
computer-use components: browser, macos, and orchestrator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime


class ActionStatus(Enum):
    """Status of an executed action."""

    SUCCESS = "success"
    """Action completed successfully."""

    FAILURE = "failure"
    """Action failed with an error."""

    TIMEOUT = "timeout"
    """Action timed out before completing."""

    NEEDS_HUMAN = "needs_human"
    """Action requires human intervention to proceed."""

    SKIPPED = "skipped"
    """Action was skipped (e.g., due to previous failure)."""


@dataclass
class ActionResult:
    """
    Result from any computer-use action.

    All browser, macos, and orchestrator actions return this type,
    providing a consistent interface for handling outcomes.

    Attributes:
        status: The outcome status of the action.
        data: Additional data returned by the action (e.g., extracted text).
        error: Error message if status is FAILURE or TIMEOUT.
        screenshot_path: Path to screenshot captured during/after action.
        duration_ms: Time taken to execute the action in milliseconds.
        timestamp: When the action was executed.

    Example:
        result = await browser.navigate("https://example.com")
        if result.succeeded:
            print(f"Loaded in {result.duration_ms}ms")
        else:
            print(f"Failed: {result.error}")
    """

    status: ActionStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    screenshot_path: str | None = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def succeeded(self) -> bool:
        """Check if action completed successfully."""
        return self.status == ActionStatus.SUCCESS

    @property
    def needs_human(self) -> bool:
        """Check if action requires human intervention."""
        return self.status == ActionStatus.NEEDS_HUMAN

    @property
    def failed(self) -> bool:
        """Check if action failed or timed out."""
        return self.status in (ActionStatus.FAILURE, ActionStatus.TIMEOUT)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "screenshot_path": self.screenshot_path,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def success(
        cls,
        data: dict[str, Any] | None = None,
        screenshot_path: str | None = None,
        duration_ms: int = 0,
    ) -> "ActionResult":
        """Create a successful result."""
        return cls(
            status=ActionStatus.SUCCESS,
            data=data or {},
            screenshot_path=screenshot_path,
            duration_ms=duration_ms,
        )

    @classmethod
    def failure(
        cls,
        error: str,
        screenshot_path: str | None = None,
        duration_ms: int = 0,
    ) -> "ActionResult":
        """Create a failure result."""
        return cls(
            status=ActionStatus.FAILURE,
            error=error,
            screenshot_path=screenshot_path,
            duration_ms=duration_ms,
        )

    @classmethod
    def timeout(
        cls,
        error: str = "Action timed out",
        screenshot_path: str | None = None,
        duration_ms: int = 0,
    ) -> "ActionResult":
        """Create a timeout result."""
        return cls(
            status=ActionStatus.TIMEOUT,
            error=error,
            screenshot_path=screenshot_path,
            duration_ms=duration_ms,
        )

    @classmethod
    def human_needed(
        cls,
        reason: str,
        screenshot_path: str | None = None,
    ) -> "ActionResult":
        """Create a result indicating human intervention is needed."""
        return cls(
            status=ActionStatus.NEEDS_HUMAN,
            data={"reason": reason},
            screenshot_path=screenshot_path,
        )


@dataclass
class HumanCheckpoint:
    """
    Request for human intervention during automation.

    When automation encounters a situation that requires human judgment
    or action (login, payment, captcha, confirmation), a HumanCheckpoint
    is created to pause execution and notify the user.

    Attributes:
        reason: Category of intervention needed.
        instructions: Clear instructions for what the human should do.
        screenshot_path: Screenshot showing current state.
        timeout_seconds: Max time to wait for human action.
        callback_url: Optional webhook to call when human completes action.

    Example:
        checkpoint = HumanCheckpoint(
            reason="login",
            instructions="Please log in to your Unity account",
            screenshot_path="/tmp/login_page.png",
        )
    """

    reason: str
    instructions: str
    screenshot_path: str | None = None
    timeout_seconds: int = 300  # 5 minutes default
    callback_url: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    # Common checkpoint reasons
    REASON_LOGIN = "login"
    REASON_PAYMENT = "payment"
    REASON_CAPTCHA = "captcha"
    REASON_CONFIRMATION = "confirmation"
    REASON_PERMISSION = "permission"
    REASON_ERROR = "error"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "reason": self.reason,
            "instructions": self.instructions,
            "screenshot_path": self.screenshot_path,
            "timeout_seconds": self.timeout_seconds,
            "callback_url": self.callback_url,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def for_login(
        cls,
        service: str = "the service",
        screenshot_path: str | None = None,
    ) -> "HumanCheckpoint":
        """Create checkpoint for login page."""
        return cls(
            reason=cls.REASON_LOGIN,
            instructions=f"Please log in to {service}. The automation will continue after you complete login.",
            screenshot_path=screenshot_path,
        )

    @classmethod
    def for_payment(
        cls,
        description: str = "this purchase",
        screenshot_path: str | None = None,
    ) -> "HumanCheckpoint":
        """Create checkpoint for payment page."""
        return cls(
            reason=cls.REASON_PAYMENT,
            instructions=f"Please complete payment for {description}. The automation will continue after payment is confirmed.",
            screenshot_path=screenshot_path,
            timeout_seconds=600,  # 10 minutes for payment
        )

    @classmethod
    def for_captcha(
        cls,
        screenshot_path: str | None = None,
    ) -> "HumanCheckpoint":
        """Create checkpoint for captcha challenge."""
        return cls(
            reason=cls.REASON_CAPTCHA,
            instructions="Please solve the captcha. The automation will continue after verification.",
            screenshot_path=screenshot_path,
            timeout_seconds=120,  # 2 minutes for captcha
        )

    @classmethod
    def for_confirmation(
        cls,
        action: str,
        screenshot_path: str | None = None,
    ) -> "HumanCheckpoint":
        """Create checkpoint for destructive/important action confirmation."""
        return cls(
            reason=cls.REASON_CONFIRMATION,
            instructions=f"Please confirm: {action}. Click 'Confirm' to proceed or 'Cancel' to abort.",
            screenshot_path=screenshot_path,
            timeout_seconds=180,  # 3 minutes for confirmation
        )

    @classmethod
    def for_permission(
        cls,
        permission: str,
        screenshot_path: str | None = None,
    ) -> "HumanCheckpoint":
        """Create checkpoint for system permission dialog."""
        return cls(
            reason=cls.REASON_PERMISSION,
            instructions=f"Please grant the requested permission: {permission}. The automation will continue after you respond to the dialog.",
            screenshot_path=screenshot_path,
            timeout_seconds=120,
        )


@dataclass
class ActionLog:
    """
    Log entry for an executed action.

    Used by the orchestrator to maintain a complete audit trail
    of all actions taken during a workflow.

    Attributes:
        action_id: Unique identifier for this action.
        module: Which module executed the action (browser, macos).
        action: Name of the action (navigate, click, etc.).
        params: Parameters passed to the action.
        result: The ActionResult from execution.
        screenshot_before: Screenshot taken before action.
        screenshot_after: Screenshot taken after action.
    """

    action_id: str
    module: str
    action: str
    params: dict[str, Any]
    result: ActionResult
    screenshot_before: str | None = None
    screenshot_after: str | None = None
    parent_action_id: str | None = None  # For nested/hierarchical actions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_id": self.action_id,
            "module": self.module,
            "action": self.action,
            "params": self.params,
            "result": self.result.to_dict(),
            "screenshot_before": self.screenshot_before,
            "screenshot_after": self.screenshot_after,
            "parent_action_id": self.parent_action_id,
        }
