#!/usr/bin/env python3
"""
orchestrator.py - Command Orchestrator for Unity Automation

This module provides a command-based interface for Unity automation workflows,
allowing integration with claude-loop CLI and workflow YAML files.

The orchestrator supports a namespace-based command system:
    unity.setup_quest3   - Full Quest 3 SDK setup workflow
    unity.build          - Build APK for Android/Quest
    unity.deploy         - Deploy APK to connected Quest device

Usage:
    from agents.computer_use.orchestrator import UnityOrchestrator

    orchestrator = UnityOrchestrator()

    # Execute a command
    result = orchestrator.execute("unity.setup_quest3")

    # Execute from workflow YAML
    result = orchestrator.execute_workflow("setup-quest3.yaml")
"""

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable

try:
    import yaml  # type: ignore
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False

from .unity import (
    UnityAgent,
    UnityWorkflows,
    WorkflowProgress,
    BuildOptions,
    BuildResult,
)


# =============================================================================
# Command Types
# =============================================================================


class CommandStatus(Enum):
    """Status of a command execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CommandResult:
    """Result of executing a command."""
    command: str
    status: CommandStatus
    message: str = ""
    duration_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WorkflowStepDefinition:
    """A step in a workflow definition."""
    command: str
    name: str = ""
    description: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    continue_on_error: bool = False
    condition: Optional[str] = None  # Simple condition like "unity.is_running"


@dataclass
class WorkflowDefinition:
    """Definition of a workflow from YAML."""
    name: str
    description: str = ""
    steps: List[WorkflowStepDefinition] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecutionResult:
    """Result of executing a complete workflow."""
    workflow_name: str
    success: bool
    message: str = ""
    duration_seconds: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    step_results: List[CommandResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# Type alias for progress callbacks
ProgressCallback = Optional[Callable[[str, float], Any]]


# =============================================================================
# Unity Command Registry
# =============================================================================


class UnityCommandRegistry:
    """
    Registry of Unity automation commands.

    Commands are organized in namespaces:
        unity.*       - Unity Editor automation
        unity.build.* - Build-related commands
        unity.xr.*    - XR/VR-related commands
    """

    def __init__(self, agent: Optional[UnityAgent] = None):
        """Initialize the command registry.

        Args:
            agent: Optional UnityAgent instance. Creates new one if not provided.
        """
        self._agent = agent or UnityAgent()
        self._workflows = UnityWorkflows(self._agent)
        self._commands: Dict[str, Callable[..., CommandResult]] = {}
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        # Core Unity commands
        self._commands["unity.is_running"] = self._cmd_is_running
        self._commands["unity.wait_idle"] = self._cmd_wait_idle
        self._commands["unity.get_project"] = self._cmd_get_project

        # Setup commands
        self._commands["unity.setup_quest3"] = self._cmd_setup_quest3
        self._commands["unity.install_meta_sdk"] = self._cmd_install_meta_sdk
        self._commands["unity.configure_xr"] = self._cmd_configure_xr

        # Build commands
        self._commands["unity.build"] = self._cmd_build
        self._commands["unity.build.apk"] = self._cmd_build_apk
        self._commands["unity.build.aab"] = self._cmd_build_aab

        # Deploy commands
        self._commands["unity.deploy"] = self._cmd_deploy
        self._commands["unity.deploy.quest"] = self._cmd_deploy_quest
        self._commands["unity.devices"] = self._cmd_list_devices

        # Dialog handling commands
        self._commands["unity.handle_dialogs"] = self._cmd_handle_dialogs

        # State detection commands
        self._commands["unity.state"] = self._cmd_get_state
        self._commands["unity.console_errors"] = self._cmd_get_console_errors

    def get_available_commands(self) -> List[str]:
        """Get list of all registered command names."""
        return sorted(self._commands.keys())

    def has_command(self, command: str) -> bool:
        """Check if a command is registered."""
        return command in self._commands

    def execute(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        progress_callback: ProgressCallback = None,
    ) -> CommandResult:
        """
        Execute a registered command.

        Args:
            command: Command name (e.g., "unity.setup_quest3").
            args: Optional arguments for the command.
            progress_callback: Optional callback for progress updates.

        Returns:
            CommandResult with execution status and details.
        """
        args = args or {}

        if not self.has_command(command):
            return CommandResult(
                command=command,
                status=CommandStatus.FAILED,
                message=f"Unknown command: {command}",
                error=f"Command '{command}' is not registered",
            )

        start_time = time.time()
        try:
            # Pass progress callback if supported
            if progress_callback:
                args["_progress_callback"] = progress_callback

            result = self._commands[command](**args)
            result.duration_seconds = time.time() - start_time
            return result

        except Exception as e:
            return CommandResult(
                command=command,
                status=CommandStatus.FAILED,
                message=f"Command failed: {str(e)}",
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Core Unity Commands
    # -------------------------------------------------------------------------

    def _cmd_is_running(self, **_: Any) -> CommandResult:
        """Check if Unity is running."""
        is_running = self._agent.is_unity_running()
        return CommandResult(
            command="unity.is_running",
            status=CommandStatus.SUCCESS,
            message="Unity is running" if is_running else "Unity is not running",
            details={"is_running": is_running},
        )

    def _cmd_wait_idle(
        self,
        timeout: float = 120.0,
        **_: Any,
    ) -> CommandResult:
        """Wait for Unity to become idle (no compilation/import)."""
        try:
            self._agent.wait_for_idle(timeout=timeout)
            return CommandResult(
                command="unity.wait_idle",
                status=CommandStatus.SUCCESS,
                message="Unity is idle",
            )
        except TimeoutError as e:
            return CommandResult(
                command="unity.wait_idle",
                status=CommandStatus.FAILED,
                message="Timeout waiting for Unity to become idle",
                error=str(e),
            )

    def _cmd_get_project(self, **_: Any) -> CommandResult:
        """Get information about the currently open Unity project."""
        project = self._agent.get_open_project()
        if project:
            return CommandResult(
                command="unity.get_project",
                status=CommandStatus.SUCCESS,
                message=f"Project: {project.name}",
                details={
                    "name": project.name,
                    "path": project.path,
                    "version": project.version,
                },
            )
        return CommandResult(
            command="unity.get_project",
            status=CommandStatus.FAILED,
            message="No Unity project is open",
            error="Unity project not detected",
        )

    # -------------------------------------------------------------------------
    # Setup Commands
    # -------------------------------------------------------------------------

    def _cmd_setup_quest3(
        self,
        install_sdk: bool = True,
        configure_xr: bool = True,
        run_meta_setup: bool = True,
        add_define_symbol: bool = True,
        _progress_callback: ProgressCallback = None,
        **_: Any,
    ) -> CommandResult:
        """Run full Quest 3 project setup workflow."""

        def on_progress(progress: WorkflowProgress) -> None:
            if _progress_callback:
                percent = progress.progress_percent or 0
                _progress_callback(progress.message, percent)

        result = self._workflows.setup_quest3_project(
            install_sdk=install_sdk,
            configure_xr=configure_xr,
            run_meta_setup=run_meta_setup,
            add_define_symbol=add_define_symbol,
            progress_callback=on_progress,
        )

        return CommandResult(
            command="unity.setup_quest3",
            status=CommandStatus.SUCCESS if result.success else CommandStatus.FAILED,
            message=result.message,
            duration_seconds=result.duration_seconds,
            details={
                "steps_completed": result.steps_completed,
                "steps_total": result.steps_total,
                "workflow_details": result.details,
            },
            error=result.errors[0] if result.errors else None,
        )

    def _cmd_install_meta_sdk(
        self,
        package_name: Optional[str] = None,
        _progress_callback: ProgressCallback = None,
        **_: Any,
    ) -> CommandResult:
        """Install Meta XR SDK from Asset Store."""

        def on_progress(progress: WorkflowProgress) -> None:
            if _progress_callback:
                percent = progress.progress_percent or 0
                _progress_callback(progress.message, percent)

        result = self._workflows.install_meta_xr_sdk(
            package_name=package_name,
            progress_callback=on_progress,
        )

        return CommandResult(
            command="unity.install_meta_sdk",
            status=CommandStatus.SUCCESS if result.success else CommandStatus.FAILED,
            message=result.message,
            duration_seconds=result.duration_seconds,
            error=result.errors[0] if result.errors else None,
        )

    def _cmd_configure_xr(
        self,
        platform: str = "Android",
        xr_plugin: str = "Oculus",
        _progress_callback: ProgressCallback = None,
        **_: Any,
    ) -> CommandResult:
        """Configure XR settings for a platform."""

        def on_progress(progress: WorkflowProgress) -> None:
            if _progress_callback:
                percent = progress.progress_percent or 0
                _progress_callback(progress.message, percent)

        # Validate platform name
        valid_platforms = ["Standalone", "Android", "iOS", "WebGL"]
        if platform not in valid_platforms:
            return CommandResult(
                command="unity.configure_xr",
                status=CommandStatus.FAILED,
                message=f"Unknown platform: {platform}",
                error=f"Valid platforms: {valid_platforms}",
            )

        result = self._workflows.configure_xr_settings(
            platform=platform,
            xr_plugin=xr_plugin,
            progress_callback=on_progress,
        )

        return CommandResult(
            command="unity.configure_xr",
            status=CommandStatus.SUCCESS if result.success else CommandStatus.FAILED,
            message=result.message,
            duration_seconds=result.duration_seconds,
            error=result.errors[0] if result.errors else None,
        )

    # -------------------------------------------------------------------------
    # Build Commands
    # -------------------------------------------------------------------------

    def _cmd_build(
        self,
        output_path: Optional[str] = None,
        development: bool = True,
        **_: Any,
    ) -> CommandResult:
        """Build the project (uses current platform settings)."""
        if output_path is None:
            output_path = "./Build/app.apk"

        build_options = BuildOptions(
            development_build=development,
            script_debugging=development,
        )

        try:
            self._agent.set_build_options(build_options)
            result_info = self._agent.build(output_path)

            success = result_info.result == BuildResult.SUCCESS

            return CommandResult(
                command="unity.build",
                status=CommandStatus.SUCCESS if success else CommandStatus.FAILED,
                message="Build completed" if success else "Build failed",
                duration_seconds=result_info.build_time_seconds,
                details={
                    "output_path": result_info.output_path,
                    "result": result_info.result.value,
                },
                error=(
                    result_info.errors[0].message
                    if result_info.errors
                    else None
                ),
            )
        except Exception as e:
            return CommandResult(
                command="unity.build",
                status=CommandStatus.FAILED,
                message=f"Build failed: {str(e)}",
                error=str(e),
            )

    def _cmd_build_apk(
        self,
        output_path: Optional[str] = None,
        development: bool = True,
        **kwargs: Any,
    ) -> CommandResult:
        """Build Android APK."""
        if output_path is None:
            output_path = "./Build/app.apk"

        # Switch to Android platform if needed
        try:
            current = self._agent.get_current_platform()
            if current and str(current) != "Android":
                self._agent.switch_platform("Android")
        except Exception:
            pass  # Continue with build attempt

        return self._cmd_build(output_path=output_path, development=development, **kwargs)

    def _cmd_build_aab(
        self,
        output_path: Optional[str] = None,
        development: bool = False,
        **kwargs: Any,
    ) -> CommandResult:
        """Build Android App Bundle (AAB)."""
        if output_path is None:
            output_path = "./Build/app.aab"

        # Switch to Android platform if needed
        try:
            current = self._agent.get_current_platform()
            if current and str(current) != "Android":
                self._agent.switch_platform("Android")

            # Enable AAB option
            build_options = BuildOptions(
                development_build=development,
                build_app_bundle=True,
            )
            self._agent.set_build_options(build_options)
        except Exception:
            pass  # Continue with build attempt

        return self._cmd_build(output_path=output_path, development=development, **kwargs)

    # -------------------------------------------------------------------------
    # Deploy Commands
    # -------------------------------------------------------------------------

    def _cmd_deploy(
        self,
        output_path: Optional[str] = None,
        device_id: Optional[str] = None,
        development: bool = True,
        _progress_callback: ProgressCallback = None,
        **_: Any,
    ) -> CommandResult:
        """Build and deploy to a connected device."""

        def on_progress(progress: WorkflowProgress) -> None:
            if _progress_callback:
                percent = progress.progress_percent or 0
                _progress_callback(progress.message, percent)

        result = self._workflows.build_and_deploy_quest(
            output_path=output_path,
            device_id=device_id,
            development_build=development,
            progress_callback=on_progress,
        )

        return CommandResult(
            command="unity.deploy",
            status=CommandStatus.SUCCESS if result.success else CommandStatus.FAILED,
            message=result.message,
            duration_seconds=result.duration_seconds,
            details=result.details or {},
            error=result.errors[0] if result.errors else None,
        )

    def _cmd_deploy_quest(
        self,
        output_path: Optional[str] = None,
        device_id: Optional[str] = None,
        development: bool = True,
        **kwargs: Any,
    ) -> CommandResult:
        """Build and deploy specifically to Quest device."""
        return self._cmd_deploy(
            output_path=output_path,
            device_id=device_id,
            development=development,
            **kwargs,
        )

    def _cmd_list_devices(self, **_: Any) -> CommandResult:
        """List connected Android/Quest devices."""
        try:
            devices = self._agent.get_connected_devices()

            device_list = []
            for device in devices:
                device_list.append({
                    "id": device.device_id,
                    "model": device.model,
                    "state": device.state,
                    "is_quest": device.is_quest,
                })

            return CommandResult(
                command="unity.devices",
                status=CommandStatus.SUCCESS,
                message=f"Found {len(devices)} device(s)",
                details={"devices": device_list},
            )
        except Exception as e:
            return CommandResult(
                command="unity.devices",
                status=CommandStatus.FAILED,
                message=f"Failed to list devices: {str(e)}",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Dialog Handling Commands
    # -------------------------------------------------------------------------

    def _cmd_handle_dialogs(
        self,
        max_dialogs: int = 10,
        timeout: float = 30.0,
        **_: Any,
    ) -> CommandResult:
        """Handle any pending Unity dialogs."""
        try:
            results = self._agent.handle_all_dialogs(
                max_dialogs=max_dialogs,
                timeout=timeout,
            )

            handled_count = sum(1 for r in results if r.handled)

            return CommandResult(
                command="unity.handle_dialogs",
                status=CommandStatus.SUCCESS,
                message=f"Handled {handled_count} dialog(s)",
                details={
                    "handled_count": handled_count,
                    "total_detected": len(results),
                    "dialogs": [
                        {
                            "type": r.dialog_type.value if r.dialog_type else "unknown",
                            "handled": r.handled,
                            "action": r.action_taken.value if r.action_taken else None,
                        }
                        for r in results
                    ],
                },
            )
        except Exception as e:
            return CommandResult(
                command="unity.handle_dialogs",
                status=CommandStatus.FAILED,
                message=f"Failed to handle dialogs: {str(e)}",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # State Detection Commands
    # -------------------------------------------------------------------------

    def _cmd_get_state(self, **_: Any) -> CommandResult:
        """Get current Unity Editor state."""
        try:
            state = self._agent.get_editor_state()

            return CommandResult(
                command="unity.state",
                status=CommandStatus.SUCCESS,
                message="Got editor state",
                details={
                    "is_compiling": state.is_compiling,
                    "is_importing": state.is_importing,
                    "is_playing": state.is_playing,
                    "has_errors": state.has_errors,
                    "error_count": state.console_error_count,
                    "warning_count": state.console_warning_count,
                },
            )
        except Exception as e:
            return CommandResult(
                command="unity.state",
                status=CommandStatus.FAILED,
                message=f"Failed to get state: {str(e)}",
                error=str(e),
            )

    def _cmd_get_console_errors(
        self,
        max_messages: int = 20,
        **_: Any,
    ) -> CommandResult:
        """Get console error messages."""
        try:
            from .unity import ConsoleMessageLevel

            messages = self._agent.get_console_messages(
                level=ConsoleMessageLevel.ERROR,
                max_messages=max_messages,
            )

            return CommandResult(
                command="unity.console_errors",
                status=CommandStatus.SUCCESS,
                message=f"Found {len(messages)} error(s)",
                details={
                    "error_count": len(messages),
                    "messages": [
                        {
                            "text": m.message,
                            "level": m.level.value,
                            "count": m.count,
                        }
                        for m in messages
                    ],
                },
            )
        except Exception as e:
            return CommandResult(
                command="unity.console_errors",
                status=CommandStatus.FAILED,
                message=f"Failed to get console errors: {str(e)}",
                error=str(e),
            )


# =============================================================================
# Workflow Executor
# =============================================================================


class WorkflowExecutor:
    """
    Executor for workflow YAML files.

    Workflow files define a sequence of Unity commands to execute.

    Example workflow YAML:
        name: setup-quest3
        description: Setup Unity project for Quest 3 development
        steps:
          - command: unity.setup_quest3
            name: Setup Quest 3 SDK
          - command: unity.build.apk
            name: Build APK
            args:
              development: true
    """

    def __init__(self, registry: Optional[UnityCommandRegistry] = None):
        """Initialize the workflow executor.

        Args:
            registry: Optional command registry. Creates new one if not provided.
        """
        self._registry = registry or UnityCommandRegistry()

    def load_workflow(self, yaml_path: str) -> WorkflowDefinition:
        """
        Load a workflow definition from a YAML file.

        Args:
            yaml_path: Path to the workflow YAML file.

        Returns:
            WorkflowDefinition parsed from the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the YAML is invalid.
        """
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required for workflow files. Install with: pip install pyyaml")

        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Workflow file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)  # type: ignore

        if not isinstance(data, dict):
            raise ValueError(f"Invalid workflow file: {yaml_path}")

        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStepDefinition(
                command=step_data.get("command", ""),
                name=step_data.get("name", ""),
                description=step_data.get("description", ""),
                args=step_data.get("args", {}),
                continue_on_error=step_data.get("continue_on_error", False),
                condition=step_data.get("condition"),
            )
            steps.append(step)

        return WorkflowDefinition(
            name=data.get("name", os.path.basename(yaml_path)),
            description=data.get("description", ""),
            steps=steps,
            variables=data.get("variables", {}),
        )

    def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        progress_callback: ProgressCallback = None,
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow definition.

        Args:
            workflow: The workflow to execute.
            progress_callback: Optional callback for progress updates.

        Returns:
            WorkflowExecutionResult with execution details.
        """
        start_time = time.time()
        step_results: List[CommandResult] = []
        errors: List[str] = []
        steps_completed = 0

        for i, step in enumerate(workflow.steps):
            step_num = i + 1
            total_steps = len(workflow.steps)

            # Report progress
            if progress_callback:
                progress = step_num / total_steps * 100
                progress_callback(
                    f"Step {step_num}/{total_steps}: {step.name or step.command}",
                    progress,
                )

            # Check condition if specified
            if step.condition:
                condition_result = self._registry.execute(step.condition)
                if condition_result.status != CommandStatus.SUCCESS:
                    step_results.append(
                        CommandResult(
                            command=step.command,
                            status=CommandStatus.SKIPPED,
                            message=f"Skipped: condition '{step.condition}' not met",
                        )
                    )
                    continue

            # Merge workflow variables with step args
            args = {**workflow.variables, **step.args}

            # Execute the command
            result = self._registry.execute(
                step.command,
                args=args,
                progress_callback=progress_callback,
            )
            step_results.append(result)

            if result.status == CommandStatus.SUCCESS:
                steps_completed += 1
            elif result.status == CommandStatus.FAILED:
                errors.append(result.error or result.message)
                if not step.continue_on_error:
                    break

        duration = time.time() - start_time
        success = len(errors) == 0 and steps_completed == len(workflow.steps)

        return WorkflowExecutionResult(
            workflow_name=workflow.name,
            success=success,
            message="Workflow completed" if success else f"Workflow failed: {errors[-1] if errors else 'Unknown error'}",
            duration_seconds=duration,
            steps_completed=steps_completed,
            steps_total=len(workflow.steps),
            step_results=step_results,
            errors=errors,
        )


# =============================================================================
# Main Orchestrator Class
# =============================================================================


class UnityOrchestrator:
    """
    Main entry point for Unity automation orchestration.

    Combines the command registry and workflow executor for easy use.

    Example:
        orchestrator = UnityOrchestrator()

        # Execute a single command
        result = orchestrator.execute("unity.setup_quest3")

        # Execute a workflow file
        result = orchestrator.execute_workflow("setup-quest3.yaml")

        # List available commands
        commands = orchestrator.get_commands()
    """

    def __init__(self, agent: Optional[UnityAgent] = None):
        """Initialize the orchestrator.

        Args:
            agent: Optional UnityAgent instance.
        """
        self._registry = UnityCommandRegistry(agent)
        self._executor = WorkflowExecutor(self._registry)

    @property
    def agent(self) -> UnityAgent:
        """Access the underlying Unity agent."""
        return self._registry._agent

    def get_commands(self) -> List[str]:
        """Get list of available commands."""
        return self._registry.get_available_commands()

    def execute(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        progress_callback: ProgressCallback = None,
    ) -> CommandResult:
        """
        Execute a Unity command.

        Args:
            command: Command name (e.g., "unity.setup_quest3").
            args: Optional command arguments.
            progress_callback: Optional progress callback.

        Returns:
            CommandResult with execution status.
        """
        return self._registry.execute(command, args, progress_callback)

    def execute_workflow(
        self,
        yaml_path: str,
        progress_callback: ProgressCallback = None,
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow from a YAML file.

        Args:
            yaml_path: Path to workflow YAML file.
            progress_callback: Optional progress callback.

        Returns:
            WorkflowExecutionResult with execution details.
        """
        workflow = self._executor.load_workflow(yaml_path)
        return self._executor.execute_workflow(workflow, progress_callback)

    def validate_workflow(self, yaml_path: str) -> List[str]:
        """
        Validate a workflow file without executing it.

        Args:
            yaml_path: Path to workflow YAML file.

        Returns:
            List of validation errors (empty if valid).
        """
        errors = []

        try:
            workflow = self._executor.load_workflow(yaml_path)
        except FileNotFoundError:
            return [f"Workflow file not found: {yaml_path}"]
        except Exception as e:
            return [f"Failed to parse workflow: {str(e)}"]

        # Validate each step
        for i, step in enumerate(workflow.steps):
            if not step.command:
                errors.append(f"Step {i + 1}: Missing command")
            elif not self._registry.has_command(step.command):
                errors.append(f"Step {i + 1}: Unknown command '{step.command}'")

            if step.condition and not self._registry.has_command(step.condition):
                errors.append(f"Step {i + 1}: Unknown condition command '{step.condition}'")

        return errors


# =============================================================================
# CLI Entry Point (for direct execution)
# =============================================================================


def main() -> None:
    """CLI entry point for the orchestrator."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <command> [args...]")
        print("       python orchestrator.py --workflow <yaml_path>")
        print()
        print("Available commands:")
        orchestrator = UnityOrchestrator()
        for cmd in orchestrator.get_commands():
            print(f"  {cmd}")
        sys.exit(0)

    orchestrator = UnityOrchestrator()

    def progress_callback(message: str, percent: float) -> None:
        print(f"[{percent:.0f}%] {message}")

    if sys.argv[1] == "--workflow":
        if len(sys.argv) < 3:
            print("Error: Missing workflow path")
            sys.exit(1)

        yaml_path = sys.argv[2]
        result = orchestrator.execute_workflow(yaml_path, progress_callback)

        print()
        print(f"Workflow: {result.workflow_name}")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Steps: {result.steps_completed}/{result.steps_total}")
        print(f"Duration: {result.duration_seconds:.1f}s")

        if result.errors:
            print(f"Errors: {', '.join(result.errors)}")

        sys.exit(0 if result.success else 1)

    else:
        command = sys.argv[1]

        # Parse remaining args as key=value pairs
        args = {}
        for arg in sys.argv[2:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                # Try to parse as JSON for complex values
                try:
                    args[key] = json.loads(value)
                except json.JSONDecodeError:
                    args[key] = value

        result = orchestrator.execute(command, args, progress_callback)

        print()
        print(f"Command: {result.command}")
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")

        if result.details:
            print(f"Details: {json.dumps(result.details, indent=2)}")

        if result.error:
            print(f"Error: {result.error}")

        sys.exit(0 if result.status == CommandStatus.SUCCESS else 1)


if __name__ == "__main__":
    main()
