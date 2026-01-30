# Claude-Loop Capacity Gaps Analysis

## Executive Summary

During the Unity Quest 3 automation workflow, several critical capacity gaps were identified in claude-loop's GUI automation capabilities. This document analyzes these gaps and proposes solutions.

## Challenges Encountered

### 1. Multi-Monitor Coordinate System Issues

**Problem**: When Unity windows are on an external monitor, AppleScript reports window positions with negative Y coordinates (e.g., -1055). Click operations fail because:
- Screenshots only capture the main display
- Coordinate calculations don't account for monitor arrangement
- Click events are sent to wrong screen locations

**Evidence**:
```
Unity main window position: {-616, -906}
Build Profiles position: {1204, -1055}
```

**Impact**: Unable to reliably click UI buttons on external monitors.

### 2. No Visual Verification

**Problem**: After triggering actions, there's no way to verify what actually happened on screen.
- AppleScript can't read Unity's custom UI elements
- No screenshot comparison to verify state changes
- Blind automation leads to silent failures

**Evidence**: Build was triggered via menu but we can't verify if a dialog appeared or if it's actually building.

### 3. Limited Dialog Detection

**Problem**: Unity shows various dialogs during operations (Input System prompt, API Update, Build errors). Current approach:
- Relies on window title matching
- Can't read dialog content
- No OCR capability to understand dialog text

**Impact**: Dialogs may block operations without detection.

### 4. No Progress Monitoring

**Problem**: Long operations (package import, builds) provide no visibility:
- Can't tell if operation is progressing or stuck
- No timeout with intelligent recovery
- Must wait arbitrary times hoping for completion

**Evidence**: Build monitoring shows "Build in progress..." for 10+ minutes with no indication if it's actually building.

### 5. No Checkpointing/Resume

**Problem**: 12-story workflow must complete sequentially:
- Failure at story 8 requires restart from story 1
- No state persistence between sessions
- Manual intervention loses context

### 6. Platform-Specific Limitations

**Problem**: AppleScript-based automation is macOS-only:
- No Windows support (pywinauto would be needed)
- No Linux support (xdotool would be needed)
- Different Unity UI behaviors per platform

## Proposed Solutions

### Solution 1: Vision-Based Click Verification (P0)

Add Claude Vision API integration for element location:

```python
class VisionBackend:
    def find_element(self, screenshot: bytes, description: str) -> tuple[int, int]:
        """Use Claude Vision to locate UI elements."""
        response = anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "data": screenshot}},
                    {"type": "text", "text": f"Find '{description}'. Return JSON: {{\"x\": N, \"y\": N, \"confidence\": 0-1}}"}
                ]
            }]
        )
        return parse_coordinates(response)
```

### Solution 2: Multi-Monitor Screenshot Capture (P0)

Use screencapture with full screen capture:

```bash
# Capture all displays
screencapture -x /tmp/all_displays.png

# Or use Python with Quartz
import Quartz
CGGetActiveDisplayList()  # Get all display IDs
CGDisplayCreateImage(displayID)  # Capture specific display
```

### Solution 3: Dialog Registry with OCR (P1)

```yaml
# .claude-loop/dialog-handlers.yaml
dialogs:
  - pattern: "Build Failed"
    detection: ocr  # Use OCR to find text
    action: capture_and_report

  - pattern: "Enable.*Input System"
    detection: vision  # Use Claude Vision
    action: click_button
    button: "Yes"
```

### Solution 4: Progress Detection via Log Monitoring (P1)

```python
class UnityProgressMonitor:
    def __init__(self, log_path: str = "~/Library/Logs/Unity/Editor.log"):
        self.log_path = log_path

    def watch_for_completion(self, timeout: int = 600) -> BuildResult:
        """Monitor Unity log for build completion."""
        with open(self.log_path, 'r') as f:
            f.seek(0, 2)  # Go to end
            start = time.time()
            while time.time() - start < timeout:
                line = f.readline()
                if "Build completed" in line:
                    return BuildResult.SUCCESS
                if "Build Failed" in line:
                    return BuildResult.FAILED
                time.sleep(0.5)
        return BuildResult.TIMEOUT
```

### Solution 5: Workflow Checkpointing (P2)

```python
class CheckpointedWorkflow:
    def __init__(self, workflow_id: str):
        self.checkpoint_file = f".claude-loop/checkpoints/{workflow_id}.json"

    def run(self, steps: list[Step]):
        completed = self.load_checkpoint()
        for step in steps:
            if step.id in completed:
                continue
            result = step.execute()
            if result.success:
                self.save_checkpoint(step.id)
            else:
                raise WorkflowError(step.id, result)
```

## Implementation Priority

| Priority | Feature | Effort | Impact | Dependencies |
|----------|---------|--------|--------|--------------|
| **P0** | Multi-monitor screenshot | Low | High | None |
| **P0** | Vision-based element finding | Medium | High | Anthropic API |
| **P1** | Unity log monitoring | Low | Medium | None |
| **P1** | Dialog OCR detection | Medium | High | pytesseract or Vision API |
| **P2** | Workflow checkpointing | Low | Medium | None |
| **P2** | Cross-platform backends | High | Medium | pywinauto, xdotool |

## Recommended Implementation Order

1. **Phase 1**: Multi-monitor support + log monitoring
   - Enable screenshots of all displays
   - Monitor Editor.log for build progress/completion

2. **Phase 2**: Vision-based automation
   - Integrate Claude Vision API for element location
   - Add click verification via before/after screenshots

3. **Phase 3**: Reliability features
   - Dialog registry with configurable handlers
   - Workflow checkpointing for long operations

## Cost Considerations

- Claude Vision API: ~$0.01-0.03 per screenshot analysis
- Expected usage: 5-10 vision calls per complex workflow
- Total cost: <$0.30 per workflow execution

---

*Analysis Date: 2026-01-11*
*Based on: Unity Quest 3 XR automation workflow experience*
