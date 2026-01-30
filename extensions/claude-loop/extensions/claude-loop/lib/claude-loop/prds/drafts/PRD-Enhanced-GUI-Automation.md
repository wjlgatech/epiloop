# PRD: Enhanced GUI Automation for claude-loop

## Problem Statement

claude-loop currently uses AppleScript for macOS GUI automation. While functional, this approach has limitations:

| Limitation | Impact |
|------------|--------|
| AppleScript failures | UI elements may not be found if window layout changes |
| No visual fallback | Cannot recover when text-based selectors fail |
| No screenshot debugging | Difficult to diagnose automation failures |
| Single-threaded dialogs | Cannot handle concurrent popups |
| No cross-platform | macOS only (no Windows/Linux support) |

## Proposed Enhancements

### Feature 1: Vision-Based Fallback

**Problem**: AppleScript selectors fail when Unity UI layout changes or custom themes are used.

**Solution**: Add Claude Vision API fallback for element detection.

```python
class UnityAgent:
    def click_element(self, element_name: str) -> bool:
        # Try AppleScript first (fast)
        if self._click_via_applescript(element_name):
            return True

        # Fallback to vision-based click (slower but robust)
        screenshot = self.screenshot()
        coordinates = self._find_element_with_vision(screenshot, element_name)
        if coordinates:
            return self._click_at_coordinates(coordinates)

        return False

    def _find_element_with_vision(self, screenshot: bytes, target: str) -> tuple[int, int]:
        """Use Claude Vision to locate UI element."""
        response = anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "data": screenshot}},
                    {"type": "text", "text": f"Find the '{target}' button/element. Return coordinates as JSON: {{\"x\": N, \"y\": N}}"}
                ]
            }]
        )
        return parse_coordinates(response)
```

**Acceptance Criteria**:
- [ ] Add `--vision-fallback` flag to enable vision-based automation
- [ ] Capture screenshot on AppleScript failure
- [ ] Use Claude Vision to locate element by description
- [ ] Click at computed coordinates using pyautogui
- [ ] Log vision requests for cost tracking

### Feature 2: Screenshot Debugging

**Problem**: When automation fails, there's no visual record of what the screen looked like.

**Solution**: Automatic screenshot capture on every action.

```python
class ActionLogger:
    def log_action(self, action: str, before: bytes, after: bytes, result: bool):
        timestamp = datetime.now().isoformat()
        log_dir = f".claude-loop/screenshots/{timestamp}/"

        save_image(f"{log_dir}/before.png", before)
        save_image(f"{log_dir}/after.png", after)
        save_json(f"{log_dir}/action.json", {
            "action": action,
            "result": result,
            "timestamp": timestamp
        })
```

**Acceptance Criteria**:
- [ ] Capture screenshot before and after each GUI action
- [ ] Save to `.claude-loop/screenshots/` with timestamps
- [ ] Generate HTML report with screenshot timeline
- [ ] Add `--no-screenshots` flag to disable (for speed)
- [ ] Cleanup old screenshots (configurable retention)

### Feature 3: Dialog Auto-Handler Registry

**Problem**: Different applications have different confirmation dialogs. Hardcoding them is not scalable.

**Solution**: Configurable dialog pattern registry.

```yaml
# .claude-loop/dialog-handlers.yaml
dialogs:
  - pattern: "Enable.*Input System"
    action: click_button
    button: "Yes"
    wait_after: 2.0

  - pattern: "API Update Required"
    action: click_button
    button: "I Made a Backup. Go Ahead!"

  - pattern: "Restart.*Editor"
    action: click_button
    button: "Yes"
    wait_after: 30.0  # Unity restart takes time

  - pattern: ".*permission.*"
    action: require_human
    message: "Permission dialog detected - manual approval required"

  - pattern: "Build Failed"
    action: capture_and_abort
    capture: ["Console", "Build Log"]
```

**Acceptance Criteria**:
- [ ] Load dialog patterns from YAML config
- [ ] Support regex patterns for dialog detection
- [ ] Support actions: click_button, require_human, capture_and_abort, ignore
- [ ] Poll for dialogs during long operations
- [ ] Log all handled dialogs

### Feature 4: Parallel Dialog Monitor

**Problem**: Dialogs can appear during any operation. Current approach checks after each action.

**Solution**: Background thread monitoring for dialogs.

```python
class DialogMonitor:
    def __init__(self, agent: UnityAgent, handlers: DialogConfig):
        self.agent = agent
        self.handlers = handlers
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = Thread(target=self._monitor_loop)
        self._thread.start()

    def _monitor_loop(self):
        while self._running:
            windows = self.agent.get_visible_windows()
            for window in windows:
                handler = self.handlers.match(window)
                if handler:
                    handler.execute(self.agent, window)
            time.sleep(0.5)
```

**Acceptance Criteria**:
- [ ] Background thread polls for dialogs every 500ms
- [ ] Thread-safe interaction with main automation
- [ ] Graceful shutdown on completion
- [ ] Don't block main workflow while handling dialogs
- [ ] Event callbacks for dialog handling

### Feature 5: Workflow Checkpoints & Resume

**Problem**: Long workflows (like SDK installation) can fail midway. Must restart from beginning.

**Solution**: Checkpoint-based workflow with resume capability.

```python
class WorkflowRunner:
    def run_with_checkpoints(self, workflow: Workflow):
        checkpoint_file = f".claude-loop/checkpoints/{workflow.id}.json"

        # Load existing checkpoint if resuming
        completed_steps = load_checkpoint(checkpoint_file) or []

        for step in workflow.steps:
            if step.id in completed_steps:
                log(f"Skipping completed step: {step.id}")
                continue

            result = step.execute()
            if result.success:
                completed_steps.append(step.id)
                save_checkpoint(checkpoint_file, completed_steps)
            else:
                raise WorkflowError(step, result)

        # Clean up checkpoint on completion
        delete_checkpoint(checkpoint_file)
```

**Acceptance Criteria**:
- [ ] Save checkpoint after each successful step
- [ ] `--resume` flag to continue from last checkpoint
- [ ] Checkpoint includes step ID, timestamp, context
- [ ] Cleanup checkpoints on successful completion
- [ ] List checkpoints command for debugging

### Feature 6: Cross-Platform Support (Windows/Linux)

**Problem**: Current implementation is macOS-only (AppleScript).

**Solution**: Abstract automation layer with platform-specific backends.

```python
class GUIBackend(ABC):
    @abstractmethod
    def activate_app(self, app_name: str) -> bool: ...

    @abstractmethod
    def click_menu(self, app: str, path: list[str]) -> bool: ...

    @abstractmethod
    def get_windows(self) -> list[str]: ...

class MacOSBackend(GUIBackend):
    """AppleScript-based backend for macOS."""
    pass

class WindowsBackend(GUIBackend):
    """pywinauto-based backend for Windows."""
    pass

class LinuxBackend(GUIBackend):
    """xdotool-based backend for Linux."""
    pass

def get_backend() -> GUIBackend:
    if sys.platform == "darwin":
        return MacOSBackend()
    elif sys.platform == "win32":
        return WindowsBackend()
    else:
        return LinuxBackend()
```

**Acceptance Criteria**:
- [ ] Abstract GUIBackend interface
- [ ] macOS: AppleScript (current implementation)
- [ ] Windows: pywinauto
- [ ] Linux: xdotool
- [ ] Runtime platform detection
- [ ] Platform-specific tests

### Feature 7: Real-Time Progress WebSocket

**Problem**: User has no visibility into long-running automation.

**Solution**: WebSocket server for real-time updates.

```python
class ProgressServer:
    def __init__(self, port: int = 7891):
        self.port = port
        self.connections = set()

    async def broadcast(self, event: dict):
        for ws in self.connections:
            await ws.send(json.dumps(event))

    def start(self):
        asyncio.create_task(websockets.serve(self.handle, "localhost", self.port))

# Usage in UnityAgent
class UnityAgent:
    def __init__(self, progress_server: ProgressServer = None):
        self.progress = progress_server

    async def install_sdk(self, sdk_name: str):
        await self.progress.broadcast({"step": "starting", "sdk": sdk_name})

        await self.progress.broadcast({"step": "downloading", "progress": 0})
        # ... download ...
        await self.progress.broadcast({"step": "downloading", "progress": 100})

        await self.progress.broadcast({"step": "importing"})
        # ... import ...

        await self.progress.broadcast({"step": "complete"})
```

**Acceptance Criteria**:
- [ ] WebSocket server on configurable port
- [ ] Progress events: started, step_begin, step_complete, error, complete
- [ ] Simple HTML client for progress visualization
- [ ] Integration with claude-loop dashboard
- [ ] Optional (--progress-server flag)

## Implementation Priority

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| **P0** | Screenshot Debugging | Low | High |
| **P0** | Dialog Auto-Handler Registry | Medium | High |
| **P1** | Vision-Based Fallback | Medium | High |
| **P1** | Parallel Dialog Monitor | Medium | Medium |
| **P2** | Workflow Checkpoints | Low | Medium |
| **P2** | Real-Time Progress | Medium | Low |
| **P3** | Cross-Platform Support | High | Medium |

## Current State Assessment

Based on ongoing Unity automation:

| Aspect | Status | Notes |
|--------|--------|-------|
| Story completion | **Working** | 2/12 completed successfully |
| AppleScript automation | **Working** | Menu navigation, window detection functional |
| Package Manager | **Working** | Registry switch, download, import working |
| Dialog handling | **Partial** | Basic handling implemented, needs registry |
| Error recovery | **Basic** | Retries on failure, no checkpoints |
| Debugging | **Limited** | Text logs only, no screenshots |

## Recommendation

**For current Unity automation task**: claude-loop IS sufficient. The existing implementation is progressing well.

**For production use**: Implement P0 features (Screenshot Debugging, Dialog Registry) to improve reliability and debuggability.

**For enterprise deployment**: Add P1 features (Vision Fallback, Parallel Dialog Monitor) for robustness.

---

*Created: 2025-01-11*
*Status: Proposal*
