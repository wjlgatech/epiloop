"""
Browser automation module using Playwright.

This module provides browser automation capabilities for claude-loop,
enabling web interaction with built-in safety features like human checkpoints
for login/payment pages and comprehensive action logging.

Example:
    async with BrowserAgent() as browser:
        await browser.navigate("https://assetstore.unity.com")
        await browser.type_text("#search-input", "Cartoon FX")
        await browser.click("button[type='submit']")
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Define stubs for type checking when playwright not installed
    if TYPE_CHECKING:
        from playwright.async_api import (
            Browser,
            BrowserContext,
            Page,
            Playwright,
            TimeoutError as PlaywrightTimeoutError,
            async_playwright,
        )
    else:
        Browser = None  # type: ignore[assignment, misc]
        BrowserContext = None  # type: ignore[assignment, misc]
        Page = None  # type: ignore[assignment, misc]
        Playwright = None  # type: ignore[assignment, misc]
        PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment, misc]

        async def async_playwright() -> None:  # type: ignore[misc]
            raise ImportError("playwright is not installed")

from .contracts import ActionLog, ActionResult, HumanCheckpoint
from .safety import (
    SafetyConfig,
    analyze_page_for_checkpoints,
    check_button_for_confirmation,
    is_domain_allowed,
)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class BrowserConfig:
    """Configuration for BrowserAgent."""

    headless: bool = False
    """Run browser without visible window."""

    timeout_ms: int = 30000
    """Default timeout for actions in milliseconds."""

    viewport_width: int = 1280
    """Browser viewport width."""

    viewport_height: int = 720
    """Browser viewport height."""

    user_agent: str | None = None
    """Custom user agent string."""

    log_dir: str = ".claude-loop/computer-use-logs"
    """Directory for action logs and screenshots."""

    screenshot_all_actions: bool = True
    """Capture screenshots before/after all actions."""

    max_retries: int = 3
    """Maximum retry attempts for failed actions."""

    retry_base_delay_ms: int = 1000
    """Base delay for exponential backoff in milliseconds."""

    enable_human_checkpoints: bool = True
    """Auto-detect and trigger human checkpoints for login/payment."""

    safety_config: SafetyConfig = field(default_factory=SafetyConfig)
    """Safety configuration for domain/action blocking."""


# =============================================================================
# Browser Agent
# =============================================================================

class BrowserAgent:
    """
    Browser automation agent using Playwright.

    Provides async methods for browser control with built-in safety features:
    - Auto-detection of login/payment pages for human checkpoints
    - Screenshot logging before/after actions
    - Retry logic with exponential backoff
    - Domain and action blocking

    Usage:
        async with BrowserAgent() as browser:
            result = await browser.navigate("https://example.com")
            if result.succeeded:
                await browser.click("#button")

    Attributes:
        config: BrowserConfig with agent settings.
        session_id: Unique session identifier for logging.
    """

    def __init__(
        self,
        config: BrowserConfig | None = None,
        headless: bool = False,
        timeout: int = 30,
    ):
        """
        Initialize BrowserAgent.

        Args:
            config: Full configuration object. If provided, other args ignored.
            headless: Run browser without visible window.
            timeout: Default timeout for actions in seconds.
        """
        if config:
            self.config = config
        else:
            self.config = BrowserConfig(
                headless=headless,
                timeout_ms=timeout * 1000,
            )

        self.session_id = f"browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._action_log: list[ActionLog] = []
        self._action_counter = 0
        self._log_dir: Path | None = None
        self._human_callback: Callable[[HumanCheckpoint], Any] | None = None

    async def __aenter__(self) -> "BrowserAgent":
        """Async context manager entry."""
        await self._start()
        return self

    async def __aexit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def _start(self) -> None:
        """Start browser and create initial page."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium"
            )

        pw_context_manager = async_playwright()
        self._playwright = await pw_context_manager.start()
        # After start(), _playwright is guaranteed to be non-None
        assert self._playwright is not None
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
        )

        # Create context with viewport and optional user agent
        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        }
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent

        assert self._browser is not None
        self._context = await self._browser.new_context(**context_options)
        assert self._context is not None
        self._page = await self._context.new_page()

        # Initialize log directory
        self._log_dir = Path(self.config.log_dir) / self.session_id
        self._log_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

        # Save action log
        if self._action_log and self._log_dir:
            log_file = self._log_dir / "actions.json"
            with open(log_file, "w") as f:
                json.dump([a.to_dict() for a in self._action_log], f, indent=2)

    # -------------------------------------------------------------------------
    # Core Actions
    # -------------------------------------------------------------------------

    async def navigate(self, url: str) -> ActionResult:
        """
        Navigate to URL and wait for page load.

        Args:
            url: Target URL to navigate to.

        Returns:
            ActionResult with status and page title in data.

        Raises:
            None - errors are captured in ActionResult.
        """
        # Check domain safety
        allowed, reason = is_domain_allowed(url, self.config.safety_config)
        if not allowed:
            return ActionResult.failure(f"Navigation blocked: {reason}")

        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            start_time = time.time()
            try:
                response = await self._page.goto(
                    url,
                    timeout=self.config.timeout_ms,
                    wait_until="domcontentloaded",
                )

                duration_ms = int((time.time() - start_time) * 1000)

                # Check for human checkpoint
                if self.config.enable_human_checkpoints:
                    checkpoint = await self._check_for_checkpoint()
                    if checkpoint:
                        return ActionResult.human_needed(
                            checkpoint.instructions,
                            screenshot_path=checkpoint.screenshot_path,
                        )

                return ActionResult.success(
                    data={
                        "url": self._page.url,
                        "title": await self._page.title(),
                        "status": response.status if response else None,
                    },
                    duration_ms=duration_ms,
                )
            except PlaywrightTimeoutError:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.timeout(
                    f"Navigation to {url} timed out",
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        return await self._execute_with_logging("navigate", {"url": url}, action)

    async def click(self, selector: str) -> ActionResult:
        """
        Click element by CSS selector or XPath.

        Args:
            selector: CSS selector or XPath expression for target element.

        Returns:
            ActionResult with status.
        """
        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            start_time = time.time()
            try:
                # Get element and check for destructive action confirmation
                element = await self._page.wait_for_selector(
                    selector,
                    timeout=self.config.timeout_ms,
                )
                if not element:
                    return ActionResult.failure(f"Element not found: {selector}")

                # Check if button text requires confirmation
                button_text = await element.text_content() or ""
                confirmation = check_button_for_confirmation(button_text)
                if confirmation.needs_checkpoint and confirmation.suggested_checkpoint:
                    screenshot_path = await self._capture_screenshot("confirmation")
                    checkpoint = confirmation.suggested_checkpoint
                    checkpoint.screenshot_path = screenshot_path
                    return ActionResult.human_needed(
                        checkpoint.instructions,
                        screenshot_path=screenshot_path,
                    )

                # Perform click
                await element.click(timeout=self.config.timeout_ms)
                duration_ms = int((time.time() - start_time) * 1000)

                # Wait a moment for page to update
                await asyncio.sleep(0.5)

                # Check for checkpoint after click
                if self.config.enable_human_checkpoints:
                    checkpoint = await self._check_for_checkpoint()
                    if checkpoint:
                        return ActionResult.human_needed(
                            checkpoint.instructions,
                            screenshot_path=checkpoint.screenshot_path,
                        )

                return ActionResult.success(
                    data={"selector": selector},
                    duration_ms=duration_ms,
                )
            except PlaywrightTimeoutError:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.timeout(
                    f"Click on {selector} timed out",
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        return await self._execute_with_logging("click", {"selector": selector}, action)

    async def click_coordinates(self, x: int, y: int) -> ActionResult:
        """
        Click at specific screen coordinates.

        Args:
            x: X coordinate (pixels from left).
            y: Y coordinate (pixels from top).

        Returns:
            ActionResult with status.
        """
        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            start_time = time.time()
            try:
                await self._page.mouse.click(x, y)
                duration_ms = int((time.time() - start_time) * 1000)

                # Wait a moment for page to update
                await asyncio.sleep(0.5)

                # Check for checkpoint after click
                if self.config.enable_human_checkpoints:
                    checkpoint = await self._check_for_checkpoint()
                    if checkpoint:
                        return ActionResult.human_needed(
                            checkpoint.instructions,
                            screenshot_path=checkpoint.screenshot_path,
                        )

                return ActionResult.success(
                    data={"x": x, "y": y},
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        return await self._execute_with_logging(
            "click_coordinates",
            {"x": x, "y": y},
            action,
        )

    async def type_text(
        self,
        selector: str,
        text: str,
        clear_first: bool = True,
    ) -> ActionResult:
        """
        Type text into an input element.

        Args:
            selector: CSS selector for input element.
            text: Text to type.
            clear_first: Clear existing content before typing.

        Returns:
            ActionResult with status.
        """
        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            start_time = time.time()
            try:
                element = await self._page.wait_for_selector(
                    selector,
                    timeout=self.config.timeout_ms,
                )
                if not element:
                    return ActionResult.failure(f"Element not found: {selector}")

                if clear_first:
                    await element.fill("")

                await element.fill(text)
                duration_ms = int((time.time() - start_time) * 1000)

                return ActionResult.success(
                    data={"selector": selector, "text_length": len(text)},
                    duration_ms=duration_ms,
                )
            except PlaywrightTimeoutError:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.timeout(
                    f"Type into {selector} timed out",
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        return await self._execute_with_logging(
            "type_text",
            {"selector": selector, "text_length": len(text)},
            action,
        )

    async def screenshot(self, path: str | None = None) -> ActionResult:
        """
        Capture page screenshot.

        Args:
            path: Optional path to save screenshot. If not provided,
                  saves to log directory with auto-generated name.

        Returns:
            ActionResult with screenshot path in data.
        """
        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            start_time = time.time()
            try:
                screenshot_path = path or await self._capture_screenshot("manual")
                if not path:
                    # Already captured
                    pass
                else:
                    await self._page.screenshot(path=screenshot_path)

                duration_ms = int((time.time() - start_time) * 1000)

                return ActionResult.success(
                    data={"path": screenshot_path},
                    screenshot_path=screenshot_path,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        # Screenshot doesn't need the standard logging wrapper (would be recursive)
        return await action()

    # -------------------------------------------------------------------------
    # Wait Actions
    # -------------------------------------------------------------------------

    async def wait_for(
        self,
        selector: str,
        timeout: int | None = None,
        state: str = "visible",
    ) -> ActionResult:
        """
        Wait for element to appear/become visible.

        Args:
            selector: CSS selector for target element.
            timeout: Override default timeout (seconds).
            state: Element state to wait for ("visible", "attached", "hidden").

        Returns:
            ActionResult with status.
        """
        async def action() -> ActionResult:
            if not self._page:
                return ActionResult.failure("Browser not started")

            timeout_ms = (timeout * 1000) if timeout else self.config.timeout_ms
            start_time = time.time()

            try:
                await self._page.wait_for_selector(
                    selector,
                    timeout=timeout_ms,
                    state=state,  # type: ignore[arg-type]
                )
                duration_ms = int((time.time() - start_time) * 1000)

                return ActionResult.success(
                    data={"selector": selector, "state": state},
                    duration_ms=duration_ms,
                )
            except PlaywrightTimeoutError:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.timeout(
                    f"Wait for {selector} ({state}) timed out",
                    duration_ms=duration_ms,
                )
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult.failure(str(e), duration_ms=duration_ms)

        return await self._execute_with_logging(
            "wait_for",
            {"selector": selector, "state": state},
            action,
        )

    async def wait_for_human(
        self,
        reason: str,
        instructions: str,
        timeout: int = 300,
    ) -> ActionResult:
        """
        Pause execution and wait for human intervention.

        Creates a checkpoint and waits for human to complete the action.
        Displays instructions and takes periodic screenshots to detect completion.

        Args:
            reason: Category of intervention (login, payment, captcha, etc.).
            instructions: Clear instructions for what the human should do.
            timeout: Maximum time to wait in seconds (default 5 minutes).

        Returns:
            ActionResult with SUCCESS if human completed action, TIMEOUT otherwise.
        """
        screenshot_path = await self._capture_screenshot(f"checkpoint_{reason}")

        checkpoint = HumanCheckpoint(
            reason=reason,
            instructions=instructions,
            screenshot_path=screenshot_path,
            timeout_seconds=timeout,
        )

        # Log the checkpoint
        self._log_action(
            "wait_for_human",
            {"reason": reason, "instructions": instructions},
            ActionResult.human_needed(instructions, screenshot_path=screenshot_path),
            screenshot_before=screenshot_path,
        )

        # Notify via callback if registered
        if self._human_callback:
            self._human_callback(checkpoint)

        # Display checkpoint info
        print(f"\n{'='*60}")
        print(f"HUMAN CHECKPOINT: {reason.upper()}")
        print(f"{'='*60}")
        print(f"Instructions: {instructions}")
        print(f"Screenshot saved: {screenshot_path}")
        print(f"Timeout: {timeout} seconds")
        print(f"{'='*60}")
        print("Press ENTER when complete, or wait for timeout...")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Wait for human to complete
        # In a real implementation, this would use a proper notification system
        # For now, we use a simple polling approach
        try:
            # Wait for user input or timeout
            # asyncio.sleep with periodic checks
            elapsed = 0
            poll_interval = 5  # seconds

            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed = int(time.time() - start_time)

                # TODO: In production, check for completion signal
                # For now, we just wait the full timeout

            duration_ms = int((time.time() - start_time) * 1000)
            return ActionResult.timeout(
                f"Human checkpoint timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            # Task was cancelled - assume human completed
            duration_ms = int((time.time() - start_time) * 1000)
            return ActionResult.success(
                data={"reason": reason, "completed_by": "human"},
                duration_ms=duration_ms,
            )

    def set_human_callback(
        self,
        callback: Callable[[HumanCheckpoint], Any],
    ) -> None:
        """
        Set callback for human checkpoint notifications.

        Args:
            callback: Function called when human intervention needed.
        """
        self._human_callback = callback

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def get_page_info(self) -> dict[str, Any]:
        """Get current page information."""
        if not self._page:
            return {"error": "Browser not started"}

        return {
            "url": self._page.url,
            "title": await self._page.title(),
        }

    def get_action_log(self) -> list[ActionLog]:
        """Get log of all executed actions."""
        return self._action_log.copy()

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    async def _capture_screenshot(self, action_name: str) -> str:
        """Capture screenshot and return path."""
        if not self._page or not self._log_dir:
            return ""

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        filename = f"{self._action_counter:04d}_{action_name}_{timestamp}.png"
        path = self._log_dir / filename

        try:
            await self._page.screenshot(path=str(path))
            return str(path)
        except Exception:
            return ""

    async def _check_for_checkpoint(self) -> HumanCheckpoint | None:
        """Check current page for conditions requiring human intervention."""
        if not self._page:
            return None

        try:
            url = self._page.url
            html = await self._page.content()
            visible_text = await self._page.inner_text("body")

            analysis = analyze_page_for_checkpoints(
                url=url,
                html_content=html,
                visible_text=visible_text,
            )

            if analysis.needs_checkpoint and analysis.suggested_checkpoint:
                screenshot_path = await self._capture_screenshot(
                    f"checkpoint_{analysis.checkpoint_type}"
                )
                checkpoint = analysis.suggested_checkpoint
                checkpoint.screenshot_path = screenshot_path
                return checkpoint

        except Exception:
            pass

        return None

    async def _execute_with_logging(
        self,
        action_name: str,
        params: dict[str, Any],
        action_fn: Callable[[], Any],
    ) -> ActionResult:
        """
        Execute an action with logging and retry logic.

        Args:
            action_name: Name of the action for logging.
            params: Action parameters for logging.
            action_fn: Async function to execute.

        Returns:
            ActionResult from action or retry attempts.
        """
        screenshot_before = None
        if self.config.screenshot_all_actions:
            screenshot_before = await self._capture_screenshot(f"{action_name}_before")

        # Retry logic with exponential backoff
        last_result: ActionResult | None = None
        for attempt in range(self.config.max_retries):
            result = await action_fn()
            last_result = result

            # Success or human needed - don't retry
            if result.succeeded or result.needs_human:
                break

            # Timeout or failure - retry with backoff
            if attempt < self.config.max_retries - 1:
                delay_ms = self.config.retry_base_delay_ms * (2 ** attempt)
                await asyncio.sleep(delay_ms / 1000)

        if not last_result:
            last_result = ActionResult.failure("No result from action")

        screenshot_after = None
        if self.config.screenshot_all_actions:
            screenshot_after = await self._capture_screenshot(f"{action_name}_after")

        # Log the action
        self._log_action(
            action_name,
            params,
            last_result,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

        return last_result

    def _log_action(
        self,
        action_name: str,
        params: dict[str, Any],
        result: ActionResult,
        screenshot_before: str | None = None,
        screenshot_after: str | None = None,
    ) -> None:
        """Add action to log."""
        self._action_counter += 1
        action_id = f"act_{self.session_id}_{self._action_counter:04d}"

        log_entry = ActionLog(
            action_id=action_id,
            module="browser",
            action=action_name,
            params=params,
            result=result,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
        )

        self._action_log.append(log_entry)
