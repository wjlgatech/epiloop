# Computer Use - Unity Automation Module

macOS automation for Unity Editor, specialized for Quest 3 XR development.

## Overview

This module provides automation capabilities for Unity Editor on macOS using AppleScript. It supports:

- **Package Manager**: Install and manage Unity packages including Meta XR SDK
- **Project Settings**: Configure XR plugins, player settings, scripting defines
- **Build Automation**: Build APKs, switch platforms, deploy to devices
- **Dialog Handling**: Automatically handle common Unity dialogs
- **State Detection**: Monitor compilation, imports, and console errors
- **Workflow Orchestration**: Run multi-step workflows via YAML files

### Enhanced GUI Automation Features (v2.0)

- **Multi-Monitor Screenshot Capture**: Capture and stitch screenshots from all connected displays, with full Retina support and coordinate mapping
- **Vision-Based Element Detection**: Use Claude Vision API to locate UI elements when AppleScript fails, with intelligent fallback
- **Log-Based Build Monitoring**: Real-time Unity Editor.log parsing for accurate build progress tracking
- **YAML-Configurable Dialog Handlers**: Define custom dialog patterns and actions in `.claude-loop/dialog-handlers.yaml`
- **Workflow Checkpointing**: Save and restore workflow progress for long-running automation tasks

## Quick Start

```python
from agents.computer_use import UnityAgent, UnityOrchestrator

# Direct agent usage
agent = UnityAgent()
if agent.is_unity_running():
    project = agent.get_open_project()
    print(f"Project: {project.name}")

# Command-based orchestration
orchestrator = UnityOrchestrator()
result = orchestrator.execute("unity.setup_quest3")
print(f"Status: {result.status}")
```

## Available Commands

### Core Unity Commands

| Command | Description |
|---------|-------------|
| `unity.is_running` | Check if Unity Editor is running |
| `unity.wait_idle` | Wait for Unity to finish compiling/importing |
| `unity.get_project` | Get info about the open Unity project |
| `unity.state` | Get current editor state (compiling, errors, etc.) |
| `unity.console_errors` | Get error messages from Console window |
| `unity.handle_dialogs` | Handle pending Unity dialogs |

### Setup Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `unity.setup_quest3` | Full Quest 3 SDK setup | `install_sdk`, `configure_xr`, `run_meta_setup`, `add_define_symbol` |
| `unity.install_meta_sdk` | Install Meta XR SDK from Asset Store | `package_name` (optional) |
| `unity.configure_xr` | Configure XR plugin settings | `platform` (default: Android), `xr_plugin` (default: Oculus) |

### Build Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `unity.build` | Build using current platform | `output_path`, `development` |
| `unity.build.apk` | Build Android APK | `output_path`, `development` |
| `unity.build.aab` | Build Android App Bundle | `output_path`, `development` |

### Deploy Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `unity.deploy` | Build and deploy to device | `output_path`, `device_id`, `development` |
| `unity.deploy.quest` | Build and deploy to Quest | `output_path`, `device_id`, `development` |
| `unity.devices` | List connected Android/Quest devices | - |

## Workflow Files

Workflows are YAML files that define a sequence of commands:

```yaml
# setup-quest3.yaml
name: setup-quest3
description: Quest 3 XR project setup

variables:
  development_build: true

steps:
  - command: unity.is_running
    name: Check Unity

  - command: unity.setup_quest3
    name: Setup SDK
    args:
      install_sdk: true
      configure_xr: true

  - command: unity.build.apk
    name: Build APK
    args:
      development: true
    continue_on_error: true
```

### Running Workflows

```bash
# Via orchestrator CLI
python3 agents/computer_use/orchestrator.py --workflow workflows/setup-quest3.yaml

# Via Python
from agents.computer_use import UnityOrchestrator

orchestrator = UnityOrchestrator()
result = orchestrator.execute_workflow("workflows/setup-quest3.yaml")
```

## Dialog Patterns

The module automatically handles common Unity dialogs:

| Dialog | Default Action | Description |
|--------|---------------|-------------|
| Input System | Accept | Enable new Input System package |
| API Update | Accept | Update deprecated APIs |
| Restart Editor | Accept | Restart to apply changes |
| Safe Mode | Reject | Don't enter safe mode (allow script fixes) |
| Build Failed | Dismiss | Capture error and close |
| Import | Accept | Confirm package imports |
| Save Scene | Accept | Save unsaved scene |
| XR Plugin | Accept | XR plugin changes |
| Android SDK | Ignore | User should configure manually |

### Configuring Dialog Handling

```python
from agents.computer_use import UnityAgent, DialogType, DialogAction, DialogConfig

agent = UnityAgent()

# Change how Safe Mode dialog is handled
agent.configure_dialog_handler(
    DialogType.SAFE_MODE,
    DialogConfig(
        action=DialogAction.ACCEPT,  # Enter safe mode
        enabled=True,
        wait_after_seconds=5.0
    )
)
```

## Safety Patterns

Import dialog patterns from the safety module:

```python
from agents.computer_use.safety import (
    UNITY_DIALOG_PATTERNS,
    get_pattern,
    get_auto_handle_patterns,
    create_custom_pattern,
)

# Get all auto-handled patterns
auto_patterns = get_auto_handle_patterns()

# Create a custom pattern
custom = create_custom_pattern(
    name="My Plugin Dialog",
    window_title_contains=["My Plugin"],
    accept_buttons=["Install"],
    auto_handle=True
)
```

## CLI Usage

The orchestrator can be run directly from command line:

```bash
# Execute a single command
python3 agents/computer_use/orchestrator.py unity.setup_quest3

# With arguments
python3 agents/computer_use/orchestrator.py unity.build.apk output_path=./Build/app.apk development=true

# Execute a workflow file
python3 agents/computer_use/orchestrator.py --workflow workflows/setup-quest3.yaml

# List available commands
python3 agents/computer_use/orchestrator.py
```

## Integration with claude-loop

Use the `--unity` flag to enable Unity mode:

```bash
./claude-loop.sh --unity
```

This enables Unity-specific agents and dialog patterns for XR development workflows.

## Requirements

- macOS (uses AppleScript for automation)
- Unity Editor installed and running
- Python 3.8+
- Optional: PyYAML (for workflow files): `pip install pyyaml`
- For deployment: Android SDK, ADB configured
- For Quest: USB connection and developer mode enabled

## Exported Classes

### From `unity.py`

- `UnityAgent` - Main automation agent
- `UnityWorkflows` - High-level workflow orchestrator
- `UnityWindow`, `UnityMenu` - Enums for windows/menus
- `Platform`, `XRPlugin` - Enums for platforms/plugins
- `BuildOptions`, `BuildResult`, `BuildResultInfo` - Build types
- `DialogType`, `DialogAction`, `DialogConfig` - Dialog handling
- `EditorState`, `ConsoleMessage` - State detection

### From `orchestrator.py`

- `UnityOrchestrator` - Command orchestrator
- `UnityCommandRegistry` - Command registry
- `WorkflowExecutor` - Workflow execution engine
- `CommandResult`, `CommandStatus` - Command results
- `WorkflowDefinition`, `WorkflowExecutionResult` - Workflow types

### From `safety.py`

- `DialogPattern` - Dialog pattern definition
- `UNITY_DIALOG_PATTERNS` - Predefined patterns
- `get_pattern`, `get_auto_handle_patterns` - Pattern helpers
- `create_custom_pattern` - Custom pattern factory

### From `screenshot.py` (v2.0)

- `MultiMonitorCapture` - Multi-monitor screenshot capture
- `DisplayInfo`, `DisplayBounds` - Display information
- `capture_screenshot` - Convenience function
- `coordinate_to_display`, `display_to_global` - Coordinate mapping

### From `unity_monitor.py` (v2.0)

- `UnityLogMonitor` - Unity Editor.log monitoring
- `BuildEventType`, `BuildPhase` - Build tracking enums
- `BuildMonitorResult` - Monitoring results
- `monitor_unity_build` - Convenience function

### From `vision_finder.py` (v2.0)

- `VisionElementFinder` - Claude Vision API integration
- `ElementLocation` - Element detection result
- `APIUsageStats` - API usage tracking

### From `click_helper.py` (v2.0)

- `ClickHelper` - Click with vision fallback
- `ClickResult`, `ClickMethod` - Click operation results

### From `dialog_registry.py` (v2.0)

- `DialogRegistry` - YAML-configurable handlers
- `DialogHandler` - Handler definition
- `DialogActionType` - Action types (click_button, capture_and_abort, etc.)
- `load_dialog_registry` - Load from YAML

### From `checkpoint.py` (v2.0)

- `WorkflowCheckpoint` - Checkpoint management
- `CheckpointData`, `CheckpointInfo` - Checkpoint types
- `list_checkpoints`, `cleanup_checkpoints` - Convenience functions

## Enhanced Features Guide (v2.0)

### Multi-Monitor Screenshot Capture

```python
from agents.computer_use import UnityAgent

agent = UnityAgent()

# Capture all displays as a panoramic image
screenshot = agent.capture_screenshot(all_displays=True)
if screenshot:
    with open("debug.png", "wb") as f:
        f.write(screenshot)

# Get display information
for display in agent.get_display_info():
    print(f"Display {display.display_id}: {display.bounds.width}x{display.bounds.height}")
    print(f"  Position: ({display.bounds.x}, {display.bounds.y})")
    print(f"  Retina: {display.is_retina}")

# Convert screenshot coordinates to screen coordinates
screen_x, screen_y = agent.screenshot_coords_to_screen(500, 300)
```

### Vision-Based Click Fallback

```python
from agents.computer_use import UnityAgent

agent = UnityAgent(enable_vision_fallback=True)

# Click using AppleScript with automatic vision fallback
result = agent.click_element(
    element_description="Build button in Build Settings window",
    window_name="Build Settings",
    vision_fallback=True,
    capture_verification=True
)

if result.success:
    print(f"Clicked via {result.method.value} at ({result.x}, {result.y})")
    print(f"Confidence: {result.confidence:.2f}")
```

### Log-Based Build Monitoring

```python
from agents.computer_use import UnityAgent

agent = UnityAgent(enable_log_monitoring=True)

# Set up progress callback
def on_progress(percent: float, message: str):
    print(f"Build: {percent:.0f}% - {message}")

agent.set_build_progress_callback(on_progress)

# Build with automatic log monitoring
result = agent.build("builds/app.apk", timeout=600.0)
if result.result == BuildResult.SUCCESS:
    print(f"Build completed in {result.build_time_seconds:.1f}s")
```

### YAML-Configurable Dialog Handlers

Create `.claude-loop/dialog-handlers.yaml`:

```yaml
handlers:
  - name: save_scene_dialog
    pattern: "Save.*Scene"
    match_type: title
    action: click_button
    action_params:
      button_name: "Save"
    priority: 10

  - name: api_update_dialog
    pattern:
      - "API Update"
      - "Obsolete API"
    match_type: title
    action: click_button
    action_params:
      button_name: "I Made a Backup"
    priority: 20

  - name: unknown_error
    pattern: "Error|Exception"
    match_type: content
    action: capture_and_abort
    priority: 100
```

```python
from agents.computer_use import UnityAgent

# Load dialog handlers from YAML
agent = UnityAgent(
    enable_dialog_registry=True,
    dialog_registry_path=".claude-loop/dialog-handlers.yaml"
)

# Handle dialogs using registry patterns
result = agent.handle_dialog(use_registry=True)
```

### Workflow Checkpointing

```python
from agents.computer_use import UnityWorkflows

workflows = UnityWorkflows(enable_checkpointing=True)

# Checkpoints are saved automatically during long workflows
result = workflows.setup_quest3_project(
    progress_callback=lambda p: print(f"{p.progress_percent:.0f}% - {p.message}")
)

# Resume from checkpoint after interruption
# (checkpoints are automatically loaded on workflow restart)
```

## Feature Availability

Some features require optional dependencies:

| Feature | Required Dependencies | Check |
|---------|----------------------|-------|
| Multi-monitor screenshots | Quartz, Pillow | `SCREENSHOT_AVAILABLE` |
| Vision element detection | anthropic SDK | `VISION_FINDER_AVAILABLE` |
| Vision click fallback | Quartz | `CLICK_HELPER_AVAILABLE` |
| YAML dialog handlers | PyYAML | `YAML_AVAILABLE` |
| Log monitoring | (standard library) | `LOG_MONITOR_AVAILABLE` |
| Checkpointing | (standard library) | `CHECKPOINT_AVAILABLE` |

```python
from agents.computer_use import (
    SCREENSHOT_AVAILABLE,
    VISION_FINDER_AVAILABLE,
    CLICK_HELPER_AVAILABLE,
    YAML_AVAILABLE,
)

# Check feature availability
print(f"Screenshots: {SCREENSHOT_AVAILABLE}")
print(f"Vision: {VISION_FINDER_AVAILABLE}")
print(f"Click Helper: {CLICK_HELPER_AVAILABLE}")
```
