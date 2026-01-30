# Gap Analysis: claude-loop Unity Editor Automation

## Executive Summary

claude-loop's current GUI automation capabilities are **insufficient for Unity Editor automation** beyond basic menu navigation. This document analyzes the specific gaps encountered while attempting to automate Quest 3 passthrough setup.

## Test Case: Quest 3 Passthrough Setup

### Required Steps
1. Open Building Blocks window (Meta > Tools > Building Blocks)
2. Click "+" button next to "Camera Rig" block
3. Click "+" button next to "Passthrough" block
4. Open Project Setup Tool (Meta > Tools > Project Setup Tool)
5. Click "Fix All" button
6. Click "Apply All" button
7. Save scene (Cmd+S)
8. Build APK (Tools > Auto Build > Build Android APK)

### Current Capabilities vs Requirements

| Step | Requirement | claude-loop Capability | Gap |
|------|-------------|----------------------|-----|
| 1 | Click menu item | ✅ AppleScript menu navigation | None |
| 2 | Click button in custom window | ❌ Cannot interact with Unity panels | **CRITICAL** |
| 3 | Click button in custom window | ❌ Cannot interact with Unity panels | **CRITICAL** |
| 4 | Click menu item | ✅ AppleScript menu navigation | None |
| 5 | Click button in custom window | ❌ Cannot interact with Unity panels | **CRITICAL** |
| 6 | Click button in custom window | ❌ Cannot interact with Unity panels | **CRITICAL** |
| 7 | Keyboard shortcut | ✅ AppleScript key code | None |
| 8 | Click menu item | ✅ AppleScript menu navigation | None |

**Success Rate: 4/8 steps (50%)**

---

## Detailed Gap Analysis

### GAP-001: No Vision-Based UI Element Detection

**Problem:** Unity Editor renders custom panels using its own UI system (IMGUI/UIElements), not native macOS UI. AppleScript cannot enumerate or interact with these elements.

**Current Behavior:**
```applescript
-- This works (native menu)
click menu item "Building Blocks" of menu "Tools" of menu bar item "Meta"

-- This fails (Unity custom window)
click button "+" of window "Building Blocks"  -- Element not found
```

**Impact:** Cannot automate any interaction within Unity Editor panels including:
- Building Blocks window
- Project Setup Tool
- Inspector panel
- Hierarchy panel
- Project panel
- Console panel

**Required Capability:** Vision API that can:
1. Take screenshot of Unity window
2. Identify UI elements by visual appearance (buttons, text fields, toggles)
3. Return coordinates for clicking

### GAP-002: No Coordinate-Based Click Fallback

**Problem:** When AppleScript element selection fails, there's no fallback to coordinate-based clicking.

**Current Behavior:**
```python
# AppleScript fails -> operation fails
# No attempt to:
# 1. Take screenshot
# 2. Use vision to find element
# 3. Click at computed coordinates
```

**Impact:** Automation stops entirely when encountering non-standard UI.

**Required Capability:**
```python
def click_element(element_name: str) -> bool:
    # Try AppleScript first
    if self._click_via_applescript(element_name):
        return True

    # Fallback: Vision-based click
    screenshot = self.screenshot()
    coords = self._find_element_with_vision(screenshot, element_name)
    if coords:
        return self._click_at_coordinates(coords)

    return False
```

### GAP-003: No Screenshot Capture Integration

**Problem:** claude-loop doesn't capture screenshots for debugging or vision analysis.

**Current Behavior:**
- No screenshots taken before/after actions
- Failures logged as text only
- No visual record for debugging

**Impact:**
- Difficult to diagnose automation failures
- No data for vision-based fallback
- No audit trail of what actually happened

**Required Capability:**
- `screencapture` integration for macOS
- Screenshot storage with timestamps
- Before/after screenshot pairs for each action

### GAP-004: No Multi-Monitor Support for Unity

**Problem:** Unity Editor often runs on external monitors. Screenshot and coordinate systems don't account for this.

**Current Behavior:**
```bash
screencapture screenshot.png  # Only captures main display
```

**Impact:** Cannot capture or click in Unity windows on external displays.

**Required Capability:**
- Detect which display contains target window
- Capture correct display
- Translate coordinates across displays

### GAP-005: No Unity-Specific Window Detection

**Problem:** No way to identify Unity Editor windows by their panel type (Building Blocks, Project Setup Tool, etc.)

**Current Behavior:**
- Can detect "Unity" application is running
- Cannot distinguish between Unity windows/panels
- Cannot detect if specific panel is open or focused

**Required Capability:**
```python
def get_unity_panels() -> List[UnityPanel]:
    """Return list of open Unity panels with their bounds."""
    # Use vision or accessibility APIs
    pass

def is_panel_open(panel_name: str) -> bool:
    """Check if specific Unity panel is visible."""
    pass
```

### GAP-006: No Wait-for-UI-State Capability

**Problem:** After opening a window, no way to wait until it's fully rendered before interacting.

**Current Behavior:**
```python
click_menu("Building Blocks")
sleep(1)  # Arbitrary sleep
click_button("+")  # May fail if window not ready
```

**Impact:** Race conditions, flaky automation.

**Required Capability:**
```python
def wait_for_panel(panel_name: str, timeout: float) -> bool:
    """Wait until panel is visible and interactive."""
    start = time.time()
    while time.time() - start < timeout:
        if self._is_panel_ready(panel_name):
            return True
        sleep(0.1)
    return False
```

### GAP-007: No Element State Detection

**Problem:** Cannot detect state of UI elements (button enabled/disabled, checkbox checked/unchecked, text field contents).

**Current Behavior:**
- Click blindly without knowing element state
- No verification that action had effect
- Cannot read error messages or status text

**Required Capability:**
```python
def get_element_state(element_name: str) -> ElementState:
    """Return state of UI element (enabled, checked, text, etc.)."""
    screenshot = self.screenshot()
    return self._analyze_element_state(screenshot, element_name)
```

---

## Root Cause Summary

| Gap ID | Root Cause | Severity |
|--------|-----------|----------|
| GAP-001 | No vision API integration | CRITICAL |
| GAP-002 | No coordinate-based fallback | CRITICAL |
| GAP-003 | No screenshot capability | HIGH |
| GAP-004 | Single-display assumption | MEDIUM |
| GAP-005 | No Unity panel detection | MEDIUM |
| GAP-006 | No UI readiness detection | MEDIUM |
| GAP-007 | No element state reading | HIGH |

---

## Recommended Solution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    claude-loop Automation                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ AppleScript │    │   Vision    │    │ Coordinate  │     │
│  │   Backend   │───▶│    API      │───▶│   Clicker   │     │
│  │  (Primary)  │    │ (Fallback)  │    │ (Fallback)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Screenshot Manager                      │   │
│  │  • Multi-display capture                            │   │
│  │  • Before/after pairs                               │   │
│  │  • Window-specific capture                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Action Logger                           │   │
│  │  • Screenshot timeline                              │   │
│  │  • Action success/failure                           │   │
│  │  • Element state before/after                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Criteria

After implementing the recommended solutions:

| Step | Expected Capability |
|------|---------------------|
| 1 | Menu click via AppleScript ✅ |
| 2 | Vision detects "+" button, coordinate click ✅ |
| 3 | Vision detects "+" button, coordinate click ✅ |
| 4 | Menu click via AppleScript ✅ |
| 5 | Vision detects "Fix All" button, coordinate click ✅ |
| 6 | Vision detects "Apply All" button, coordinate click ✅ |
| 7 | Keyboard shortcut via AppleScript ✅ |
| 8 | Menu click via AppleScript ✅ |

**Target Success Rate: 8/8 steps (100%)**

---

*Created: 2026-01-11*
*Author: Claude Code Analysis*
