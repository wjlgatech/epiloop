# PRD: Computer Use Module for claude-loop

**Version:** 1.0
**Author:** Wu & Claude
**Date:** January 2025
**Status:** Draft

---

## 1. Problem Statement

claude-loop currently automates **code changes** but cannot interact with **GUI applications**. Many Physical AI workflows require:

- Downloading assets from Unity Asset Store
- Importing packages into Unity Editor
- Managing files in macOS Finder
- Interacting with web applications that require authentication

**The core problem:** claude-loop cannot complete end-to-end workflows that span code + GUI interactions.

**What we're building:** A minimal, focused computer-use module that enables claude-loop to automate browsers and macOS applications when code automation alone is insufficient.

**What we're NOT building:** A general-purpose automation framework for arbitrary applications. We prioritize reliability over breadth.

---

## 2. Scope Constraints

### In Scope
- Browser automation (Playwright-based)
- macOS app control (AppleScript/osascript)
- Human checkpoints for login/auth/payment
- Integration with claude-loop's existing agent system

### Out of Scope (Removed from Research PRD)
| Removed | Reason |
|---------|--------|
| MCP Protocol | claude-loop uses Claude CLI, not Claude Desktop |
| Terminal Server | Claude Code already handles terminal operations |
| Cloud CLI Server | Not needed for GUI automation use cases |
| Isaac Sim Server | Specialized simulation - add later if needed |
| Cosmos Integration | Beyond current scope |
| Multi-cloud orchestration | Not relevant to GUI automation |

---

## 3. Architecture

### 3.1 Integration with claude-loop

```
┌─────────────────────────────────────────────────────────────────┐
│                      claude-loop.sh                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Claude Code (LLM)                        │    │
│  │         planning, reasoning, code changes                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              │ imports & calls                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              agents/computer-use/                        │    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐  │    │
│  │  │   browser.py  │ │   macos.py    │ │orchestrator.py│  │    │
│  │  │  (Playwright) │ │  (osascript)  │ │  (coordinator)│  │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Execution Layer                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Browsers (Chromium)  │  macOS Apps (Unity, Finder)     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Design Principles

1. **Python modules, not servers** - Direct imports from claude-loop agents
2. **Minimal dependencies** - Playwright + pyautogui + anthropic (for vision)
3. **Human-in-the-loop** - Mandatory checkpoints for auth, payment, destructive actions
4. **Fail-safe defaults** - Require confirmation, timeout on all actions
5. **Logging for debugging** - All actions logged for replay/debugging

---

## 4. Core Contracts

Adapted from research PRD - simplified for our use case:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime

class ActionStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    NEEDS_HUMAN = "needs_human"  # Requires human intervention

@dataclass
class ActionResult:
    """Result from any computer-use action"""
    status: ActionStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    screenshot_path: str | None = None  # Path to screenshot if captured
    duration_ms: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == ActionStatus.SUCCESS

@dataclass
class HumanCheckpoint:
    """Request for human intervention"""
    reason: str  # "login", "payment", "confirmation", "captcha"
    instructions: str  # What the human needs to do
    screenshot_path: str | None = None
    timeout_seconds: int = 300  # 5 min default for human actions
```

---

## 5. Module Specifications

### 5.1 Browser Module (`agents/computer-use/browser.py`)

**Purpose:** Automate web browsers using Playwright

```python
class BrowserAgent:
    """
    Browser automation via Playwright

    Supported Actions:
    - navigate(url) - Go to URL
    - click(selector) - Click element by CSS selector
    - click_coordinates(x, y) - Click at screen coordinates
    - type_text(selector, text) - Type into element
    - screenshot(path?) - Capture page screenshot
    - extract_text(selector?) - Extract text content
    - wait_for(selector, timeout) - Wait for element
    - scroll(direction, amount) - Scroll page

    Human Checkpoints:
    - Automatically triggered for login pages (detects password fields)
    - Automatically triggered for payment pages (detects card inputs)
    - Manual trigger via request_human_help(reason, instructions)
    """

    def __init__(self, headless: bool = False, timeout: int = 30):
        """
        Args:
            headless: Run browser without visible window
            timeout: Default timeout for actions in seconds
        """
        pass

    async def navigate(self, url: str) -> ActionResult:
        """Navigate to URL, wait for page load"""
        pass

    async def click(self, selector: str) -> ActionResult:
        """Click element by CSS selector or XPath"""
        pass

    async def type_text(self, selector: str, text: str,
                        clear_first: bool = True) -> ActionResult:
        """Type text into input element"""
        pass

    async def screenshot(self, path: str | None = None) -> ActionResult:
        """Capture screenshot, return path in result.data['path']"""
        pass

    async def wait_for_human(self, reason: str,
                             instructions: str) -> ActionResult:
        """
        Pause execution and wait for human to complete action.
        Shows notification, takes periodic screenshots to detect completion.
        """
        pass

    async def close(self):
        """Clean up browser resources"""
        pass
```

**Key Features:**
- Auto-detects login/payment pages and pauses for human
- Screenshots before and after each action for debugging
- Retry logic with exponential backoff
- Cookie persistence across sessions

### 5.2 macOS Module (`agents/computer-use/macos.py`)

**Purpose:** Control macOS applications via AppleScript/osascript

```python
class MacOSAgent:
    """
    macOS automation via AppleScript/osascript

    Supported Actions:
    - activate_app(name) - Bring app to foreground
    - menu_click(app, menu, item) - Click menu item
    - keyboard_shortcut(keys) - Send keyboard shortcut
    - type_text(text) - Type text at cursor
    - wait_for_window(title, timeout) - Wait for window to appear
    - get_frontmost_app() - Get name of active app
    - screenshot(path?) - Capture screen
    - finder_open(path) - Open path in Finder
    - finder_select(paths) - Select items in Finder

    Human Checkpoints:
    - Triggered for permission dialogs
    - Triggered for app crashes/errors
    """

    def __init__(self, timeout: int = 30):
        pass

    async def activate_app(self, app_name: str) -> ActionResult:
        """Bring application to foreground, launch if not running"""
        pass

    async def menu_click(self, app_name: str, menu_path: list[str]) -> ActionResult:
        """
        Click through menu hierarchy.
        Example: menu_click("Unity", ["File", "Build Settings..."])
        """
        pass

    async def keyboard_shortcut(self, *keys: str) -> ActionResult:
        """
        Send keyboard shortcut.
        Example: keyboard_shortcut("command", "shift", "s")
        """
        pass

    async def wait_for_window(self, title_contains: str,
                               timeout: int = 30) -> ActionResult:
        """Wait for window with title containing given text"""
        pass

    async def screenshot(self, path: str | None = None,
                         window: str | None = None) -> ActionResult:
        """Capture screen or specific window"""
        pass
```

**Key Features:**
- Uses osascript for native macOS integration
- Handles permission dialogs gracefully
- Window state detection via AppleScript
- Integrates with Accessibility API when needed

### 5.3 Orchestrator Module (`agents/computer-use/orchestrator.py`)

**Purpose:** Coordinate multi-step workflows across browser and macOS

```python
class ComputerUseOrchestrator:
    """
    Coordinates browser and macOS automation for complex workflows.

    Features:
    - Parse high-level instructions into action sequences
    - State tracking across actions
    - Error recovery and retry
    - Human checkpoint coordination
    - Action logging for debugging
    """

    def __init__(self,
                 browser: BrowserAgent | None = None,
                 macos: MacOSAgent | None = None,
                 log_dir: str = ".claude-loop/computer-use-logs"):
        pass

    async def execute_workflow(self, instructions: str) -> ActionResult:
        """
        Execute a high-level workflow instruction.

        Example:
            "Download 'Cartoon FX' from Unity Asset Store and import into project"

        Returns ActionResult with status and any data produced.
        """
        pass

    async def execute_step(self, step: dict) -> ActionResult:
        """
        Execute a single workflow step.

        Step format:
        {
            "module": "browser" | "macos",
            "action": "navigate" | "click" | ...,
            "params": {...},
            "on_failure": "retry" | "skip" | "abort" | "human"
        }
        """
        pass

    def get_action_log(self) -> list[dict]:
        """Get log of all executed actions for debugging"""
        pass
```

**Key Features:**
- Workflow state machine
- Cross-module coordination (download in browser → import in Unity)
- Comprehensive action logging
- Configurable failure handling

---

## 6. Safety Framework

### 6.1 Human Checkpoints (Mandatory)

| Trigger | Reason |
|---------|--------|
| Password field detected | Login required |
| Card/payment input detected | Payment required |
| Permission dialog in macOS | System permission needed |
| `confirm` or `delete` in button text | Destructive action |
| Action timeout | Manual intervention needed |
| Captcha detected | Anti-bot challenge |

### 6.2 Action Safeguards

```python
# All actions have these safeguards by default
DEFAULT_SAFEGUARDS = {
    "timeout_seconds": 30,        # Max time per action
    "screenshot_before": True,    # Capture state before
    "screenshot_after": True,     # Capture state after
    "max_retries": 3,             # Retry on transient failures
    "require_confirmation": False, # Override per-action
}

# Actions that ALWAYS require confirmation
ALWAYS_CONFIRM = [
    "delete", "remove", "uninstall",
    "purchase", "buy", "checkout",
    "submit", "send", "publish",
]
```

### 6.3 Audit Logging

All actions logged to `.claude-loop/computer-use-logs/`:

```json
{
  "timestamp": "2025-01-10T15:30:00Z",
  "module": "browser",
  "action": "click",
  "params": {"selector": "#download-button"},
  "result": {"status": "success", "duration_ms": 234},
  "screenshots": {
    "before": "logs/2025-01-10/click_001_before.png",
    "after": "logs/2025-01-10/click_001_after.png"
  }
}
```

---

## 7. Project Structure

```
claude-loop/
├── agents/
│   └── computer-use/
│       ├── __init__.py
│       ├── browser.py          # Playwright browser automation
│       ├── macos.py            # AppleScript/osascript automation
│       ├── orchestrator.py     # Multi-step workflow coordinator
│       ├── contracts.py        # ActionResult, HumanCheckpoint
│       ├── safety.py           # Checkpoint detection, confirmations
│       ├── requirements.txt    # Python dependencies
│       └── README.md           # Usage documentation
└── .claude-loop/
    └── computer-use-logs/      # Action logs and screenshots
```

---

## 8. Dependencies

```
# agents/computer-use/requirements.txt
playwright>=1.40.0      # Browser automation
pyautogui>=0.9.54       # Screen capture, fallback input
pillow>=10.0.0          # Image processing
anthropic>=0.18.0       # Vision API for UI analysis (optional)
```

**System Requirements:**
- macOS 10.15+ (for AppleScript support)
- Python 3.10+
- Playwright browsers: `playwright install chromium`
- Accessibility permissions for osascript

---

## 9. User Stories (for prd-p2.json)

### US-005: Create computer-use agent framework
**Priority:** 5

**Acceptance Criteria:**
- [ ] Create `agents/computer-use/` directory structure
- [ ] Create `contracts.py` with ActionResult, ActionStatus, HumanCheckpoint
- [ ] Create `safety.py` with checkpoint detection logic
- [ ] Create `requirements.txt` with dependencies
- [ ] Create `README.md` with usage documentation

### US-006: Implement browser automation module
**Priority:** 6

**Acceptance Criteria:**
- [ ] Create `browser.py` with BrowserAgent class
- [ ] Implement: navigate, click, type_text, screenshot, wait_for
- [ ] Auto-detect login/payment pages for human checkpoints
- [ ] Add retry logic with exponential backoff
- [ ] Add action logging with before/after screenshots

### US-007: Implement macOS app automation module
**Priority:** 7

**Acceptance Criteria:**
- [ ] Create `macos.py` with MacOSAgent class
- [ ] Implement: activate_app, menu_click, keyboard_shortcut, type_text
- [ ] Implement: wait_for_window, screenshot, finder_open
- [ ] Handle permission dialogs gracefully
- [ ] Add action logging

### US-008: Create computer-use orchestrator
**Priority:** 8

**Acceptance Criteria:**
- [ ] Create `orchestrator.py` with ComputerUseOrchestrator class
- [ ] Implement execute_workflow for high-level instructions
- [ ] Coordinate between browser and macos modules
- [ ] Implement error recovery with retry and human fallback
- [ ] Log all actions for debugging

---

## 10. Example Workflows

### Workflow A: Download Unity Asset Store Package

```python
# High-level instruction:
"Download 'Cartoon FX Remaster' from Unity Asset Store"

# Decomposed steps:
1. [browser] navigate("https://assetstore.unity.com")
2. [browser] type_text("#search-input", "Cartoon FX Remaster")
3. [browser] click("button[type='submit']")
4. [browser] wait_for(".asset-card")
5. [browser] click(".asset-card:first-child")
6. [browser] wait_for_human("login", "Please log in to Unity")  # If needed
7. [browser] click("#add-to-my-assets")  # Or "Open in Unity"
8. [macos] wait_for_window("Unity Editor")
9. [macos] menu_click("Unity", ["Window", "Package Manager"])
10. [macos] wait_for_window("Package Manager")
```

### Workflow B: Import Downloaded Package

```python
# High-level instruction:
"Import the Cartoon FX package into the current Unity project"

# Decomposed steps:
1. [macos] activate_app("Unity")
2. [macos] menu_click("Unity", ["Assets", "Import Package", "Custom Package..."])
3. [macos] wait_for_window("Import package")
4. [macos] finder_open("~/Downloads/CartoonFX.unitypackage")
5. [macos] wait_for_window("Import Unity Package")
6. [macos] click_button("Import")
7. [macos] wait_for_window("Importing")  # Wait for import to complete
```

---

## 11. Comparison with Research PRD

| Aspect | Research PRD | This PRD |
|--------|--------------|----------|
| Architecture | 6 MCP Servers | 3 Python modules |
| Protocol | MCP JSON-RPC | Direct Python imports |
| Dependencies | ~15 packages | 4 packages |
| Cloud Integration | Azure/AWS/GCP | None (not needed) |
| Simulation | Isaac Sim, Cosmos | None (not needed) |
| Implementation | 5-6 weeks | 4 user stories |
| Terminal Ops | Dedicated server | Use Claude Code |
| Target | Claude Desktop | claude-loop CLI |

---

## 12. Open Questions

1. **Vision fallback:** Should we use Claude's vision API for UI element detection when selectors fail?
2. **Credential storage:** How should we handle saved sessions/cookies securely?
3. **Parallel execution:** Should orchestrator support running browser + macOS actions in parallel?
4. **Windows support:** Should macos.py have a Windows equivalent later?

---

## 13. Next Steps

1. Review and approve this PRD
2. Update `prd-p2.json` with refined user stories (US-005 through US-008)
3. Begin implementation with US-005 (framework structure)
4. Test with Unity Asset Store workflow as validation

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial PRD - streamlined from research PRD |
