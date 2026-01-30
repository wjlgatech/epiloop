#!/usr/bin/env python3
"""
Tests for dialog_registry.py - Dialog Handler Registry

Tests cover:
- DialogHandler creation and pattern matching
- DialogRegistry loading from dict/YAML
- Dialog matching with regex patterns
- Action execution (click_button, capture_and_abort, require_human, ignore)
- Logging functionality
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.computer_use.dialog_registry import (
    DialogActionResult,
    DialogActionType,
    DialogHandler,
    DialogLogEntry,
    DialogMatchResult,
    DialogMatchType,
    DialogRegistry,
    YAML_AVAILABLE,
    create_default_config,
    load_dialog_registry,
)


# =============================================================================
# DialogHandler Tests
# =============================================================================


class TestDialogHandler:
    """Tests for DialogHandler class."""

    def test_handler_creation_simple_pattern(self):
        """Test creating a handler with a simple regex pattern."""
        handler = DialogHandler(
            name="test_handler",
            pattern="save.*scene",
        )
        assert handler.name == "test_handler"
        assert handler.pattern == "save.*scene"
        assert handler.match_type == DialogMatchType.TITLE
        assert handler.action == DialogActionType.CLICK_BUTTON
        assert handler.enabled is True

    def test_handler_creation_list_patterns(self):
        """Test creating a handler with multiple patterns."""
        handler = DialogHandler(
            name="test_handler",
            pattern=["save.*scene", "unsaved.*changes"],
        )
        assert len(handler._compiled_patterns) == 2

    def test_handler_matches_title(self):
        """Test matching against window title."""
        handler = DialogHandler(
            name="save_handler",
            pattern="save.*scene",
            match_type=DialogMatchType.TITLE,
        )
        assert handler.matches(title="Save Scene?") is True
        assert handler.matches(title="Close Window") is False
        assert handler.matches(content="Save Scene?") is False

    def test_handler_matches_content(self):
        """Test matching against dialog content."""
        handler = DialogHandler(
            name="content_handler",
            pattern="unsaved.*changes",
            match_type=DialogMatchType.CONTENT,
        )
        assert handler.matches(content="You have unsaved changes") is True
        assert handler.matches(content="All saved") is False
        assert handler.matches(title="You have unsaved changes") is False

    def test_handler_matches_both(self):
        """Test matching against both title and content."""
        handler = DialogHandler(
            name="both_handler",
            pattern="error",
            match_type=DialogMatchType.BOTH,
        )
        assert handler.matches(title="Error Dialog") is True
        assert handler.matches(content="An error occurred") is True
        assert handler.matches(title="Success", content="Completed") is False

    def test_handler_case_insensitive_match(self):
        """Test that matching is case-insensitive."""
        handler = DialogHandler(
            name="case_test",
            pattern="API.*Update",
        )
        assert handler.matches(title="api update required") is True
        assert handler.matches(title="API UPDATE REQUIRED") is True
        assert handler.matches(title="Api Update Required") is True

    def test_handler_disabled(self):
        """Test that disabled handlers don't match."""
        handler = DialogHandler(
            name="disabled_handler",
            pattern="test",
            enabled=False,
        )
        assert handler.matches(title="test dialog") is False

    def test_handler_invalid_regex_graceful(self):
        """Test that invalid regex patterns are handled gracefully."""
        # Invalid regex with unbalanced brackets
        handler = DialogHandler(
            name="invalid_regex",
            pattern="test[invalid",
        )
        # Should not raise, but patterns won't compile
        assert len(handler._compiled_patterns) == 0

    def test_handler_multiple_patterns_any_match(self):
        """Test that any of multiple patterns can trigger a match."""
        handler = DialogHandler(
            name="multi_pattern",
            pattern=["pattern_one", "pattern_two", "pattern_three"],
        )
        assert handler.matches(title="pattern_one here") is True
        assert handler.matches(title="pattern_two here") is True
        assert handler.matches(title="pattern_three here") is True
        assert handler.matches(title="pattern_four") is False


# =============================================================================
# DialogRegistry Tests
# =============================================================================


class TestDialogRegistry:
    """Tests for DialogRegistry class."""

    def test_empty_registry(self):
        """Test creating an empty registry."""
        registry = DialogRegistry()
        assert len(registry) == 0
        assert registry.match_dialog(title="test") is None

    def test_registry_from_dict(self):
        """Test loading registry from dictionary config."""
        config = {
            'handlers': [
                {
                    'name': 'test_handler',
                    'pattern': 'test.*dialog',
                    'action': 'click_button',
                    'action_params': {'button': 'OK'},
                }
            ]
        }
        registry = DialogRegistry.from_dict(config)
        assert len(registry) == 1
        assert registry.handlers[0].name == 'test_handler'

    def test_registry_from_dict_multiple_handlers(self):
        """Test loading registry with multiple handlers."""
        config = {
            'handlers': [
                {
                    'name': 'handler_1',
                    'pattern': 'first',
                    'priority': 10,
                },
                {
                    'name': 'handler_2',
                    'pattern': 'second',
                    'priority': 5,
                },
            ]
        }
        registry = DialogRegistry.from_dict(config)
        assert len(registry) == 2
        # Should be sorted by priority (handler_2 first)
        assert registry.handlers[0].name == 'handler_2'
        assert registry.handlers[1].name == 'handler_1'

    def test_registry_add_handler(self):
        """Test adding a handler to the registry."""
        registry = DialogRegistry()
        handler = DialogHandler(name="added", pattern="test")
        registry.add_handler(handler)
        assert len(registry) == 1
        assert registry.get_handler("added") is not None

    def test_registry_remove_handler(self):
        """Test removing a handler from the registry."""
        registry = DialogRegistry()
        registry.add_handler(DialogHandler(name="to_remove", pattern="test"))
        assert len(registry) == 1
        assert registry.remove_handler("to_remove") is True
        assert len(registry) == 0
        assert registry.remove_handler("nonexistent") is False

    def test_registry_match_dialog(self):
        """Test matching a dialog against the registry."""
        registry = DialogRegistry.from_dict({
            'handlers': [
                {
                    'name': 'save_handler',
                    'pattern': 'save',
                    'priority': 10,
                },
            ]
        })
        result = registry.match_dialog(title="Save Changes?")
        assert result is not None
        assert result.handler.name == 'save_handler'
        assert 'Save' in result.matched_text

    def test_registry_match_priority_order(self):
        """Test that higher priority handlers match first."""
        registry = DialogRegistry.from_dict({
            'handlers': [
                {
                    'name': 'low_priority',
                    'pattern': 'dialog',
                    'priority': 100,
                },
                {
                    'name': 'high_priority',
                    'pattern': 'dialog',
                    'priority': 1,
                },
            ]
        })
        result = registry.match_dialog(title="Test Dialog")
        assert result is not None
        assert result.handler.name == 'high_priority'

    def test_registry_no_match(self):
        """Test when no handler matches."""
        registry = DialogRegistry.from_dict({
            'handlers': [
                {
                    'name': 'save_handler',
                    'pattern': 'save',
                },
            ]
        })
        result = registry.match_dialog(title="Load File")
        assert result is None


# =============================================================================
# Action Execution Tests
# =============================================================================


class TestActionExecution:
    """Tests for action execution."""

    def test_execute_click_button_with_callback(self):
        """Test click_button action with callback."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'click_test',
                'pattern': 'test',
                'action': 'click_button',
                'action_params': {'button': 'OK'},
            }]
        })

        mock_callback = MagicMock(return_value=True)
        registry.set_button_click_callback(mock_callback)

        result = registry.match_dialog(title="test dialog")
        action_result = registry.execute_action(result, dialog_title="test dialog")

        assert action_result.success is True
        assert action_result.action_type == DialogActionType.CLICK_BUTTON
        mock_callback.assert_called_once_with('OK')

    def test_execute_click_button_multiple_buttons(self):
        """Test click_button with multiple button options."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'multi_button',
                'pattern': 'test',
                'action': 'click_button',
                'action_params': {'buttons': ['Save', 'Yes', 'OK']},
            }]
        })

        # Callback returns False for 'Save', True for 'Yes'
        call_count = [0]

        def mock_callback(button):
            call_count[0] += 1
            return button == 'Yes'

        registry.set_button_click_callback(mock_callback)

        result = registry.match_dialog(title="test dialog")
        action_result = registry.execute_action(result)

        assert action_result.success is True
        assert call_count[0] == 2  # Called for 'Save' and 'Yes'

    def test_execute_require_human(self):
        """Test require_human action."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'human_required',
                'pattern': 'license',
                'action': 'require_human',
                'action_params': {'message': 'Please handle license dialog'},
            }]
        })

        mock_human_callback = MagicMock()
        registry.set_human_callback(mock_human_callback)

        result = registry.match_dialog(title="License Expired")
        action_result = registry.execute_action(result)

        assert action_result.success is True
        assert action_result.action_type == DialogActionType.REQUIRE_HUMAN
        assert action_result.requires_human is True
        mock_human_callback.assert_called_once_with('Please handle license dialog')

    def test_execute_ignore(self):
        """Test ignore action."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'ignore_telemetry',
                'pattern': 'telemetry',
                'action': 'ignore',
                'action_params': {'reason': 'Ignoring telemetry prompt'},
            }]
        })

        result = registry.match_dialog(title="Telemetry Settings")
        action_result = registry.execute_action(result)

        assert action_result.success is True
        assert action_result.action_type == DialogActionType.IGNORE
        assert 'Ignoring' in action_result.message

    def test_execute_capture_and_abort(self):
        """Test capture_and_abort action."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'capture_error',
                'pattern': 'fatal.*error',
                'action': 'capture_and_abort',
                'action_params': {'reason': 'Fatal error detected'},
            }]
        })

        # Mock screenshot callback
        mock_screenshot = MagicMock(return_value=b'PNG_DATA_HERE')
        registry.set_screenshot_callback(mock_screenshot)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch the screenshot directory
            with patch('agents.computer_use.dialog_registry.Path') as MockPath:
                mock_path = MagicMock()
                mock_path.mkdir = MagicMock()
                mock_path.__truediv__ = MagicMock(return_value=Path(tmpdir) / "test.png")
                MockPath.return_value = mock_path

                result = registry.match_dialog(title="Fatal Error Occurred")
                action_result = registry.execute_action(result)

        assert action_result.success is True
        assert action_result.action_type == DialogActionType.CAPTURE_AND_ABORT
        assert 'Fatal error detected' in action_result.message
        mock_screenshot.assert_called_once()


# =============================================================================
# Logging Tests
# =============================================================================


class TestLogging:
    """Tests for dialog handling logs."""

    def test_log_entry_created(self):
        """Test that a log entry is created after handling."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'log_test',
                'pattern': 'test',
                'action': 'ignore',
            }]
        })

        result = registry.match_dialog(title="test dialog")
        registry.execute_action(result, dialog_title="test dialog", dialog_content="content")

        log = registry.get_log()
        assert len(log) == 1
        assert log[0].handler_name == 'log_test'
        assert log[0].dialog_title == "test dialog"
        assert log[0].dialog_content == "content"
        assert log[0].action_type == DialogActionType.IGNORE

    def test_log_multiple_entries(self):
        """Test multiple log entries."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'log_test',
                'pattern': '.*',
                'action': 'ignore',
            }]
        })

        for i in range(5):
            result = registry.match_dialog(title=f"dialog {i}")
            registry.execute_action(result)

        assert len(registry.get_log()) == 5

    def test_log_clear(self):
        """Test clearing the log."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'log_test',
                'pattern': 'test',
                'action': 'ignore',
            }]
        })

        result = registry.match_dialog(title="test")
        registry.execute_action(result)
        assert len(registry.get_log()) == 1

        registry.clear_log()
        assert len(registry.get_log()) == 0

    def test_log_summary(self):
        """Test log summary statistics."""
        registry = DialogRegistry.from_dict({
            'handlers': [
                {'name': 'handler_a', 'pattern': 'pattern_a', 'action': 'ignore'},
                {'name': 'handler_b', 'pattern': 'pattern_b', 'action': 'click_button'},
            ]
        })

        # Add click callback that succeeds
        registry.set_button_click_callback(lambda _: True)

        # Trigger handler_a twice
        for _ in range(2):
            result = registry.match_dialog(title="pattern_a here")
            registry.execute_action(result)

        # Trigger handler_b once
        result = registry.match_dialog(title="pattern_b here")
        registry.execute_action(result)

        summary = registry.get_log_summary()
        assert summary['total_handled'] == 3
        assert summary['by_handler']['handler_a'] == 2
        assert summary['by_handler']['handler_b'] == 1
        assert summary['by_action']['ignore'] == 2
        assert summary['by_action']['click_button'] == 1
        assert summary['successful'] == 3


# =============================================================================
# YAML Loading Tests
# =============================================================================


@pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not installed")
class TestYAMLLoading:
    """Tests for YAML configuration loading."""

    def test_load_from_yaml_file(self):
        """Test loading registry from YAML file."""
        yaml_content = """
handlers:
  - name: yaml_handler
    pattern: "test.*pattern"
    action: click_button
    action_params:
      button: OK
    priority: 10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            registry = DialogRegistry.from_yaml(f.name)

        assert len(registry) == 1
        assert registry.handlers[0].name == 'yaml_handler'
        assert registry.handlers[0].priority == 10

    def test_load_nonexistent_yaml(self):
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            DialogRegistry.from_yaml("/nonexistent/path.yaml")

    def test_load_empty_yaml(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            f.flush()

            registry = DialogRegistry.from_yaml(f.name)

        assert len(registry) == 0

    def test_load_yaml_with_invalid_handler(self):
        """Test that invalid handlers are skipped."""
        yaml_content = """
handlers:
  - name: valid_handler
    pattern: "test"
  - invalid_entry_without_name: true
  - name: another_valid
    pattern: "test2"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            registry = DialogRegistry.from_yaml(f.name)

        # Should have 2 valid handlers (invalid one skipped)
        assert len(registry) == 2

    def test_to_yaml_roundtrip(self):
        """Test saving and loading YAML produces same registry."""
        original = DialogRegistry.from_dict({
            'handlers': [
                {
                    'name': 'roundtrip_test',
                    'pattern': 'test.*pattern',
                    'action': 'click_button',
                    'action_params': {'button': 'OK'},
                    'priority': 42,
                    'description': 'Test description',
                }
            ]
        })

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name

        original.to_yaml(temp_path)
        loaded = DialogRegistry.from_yaml(temp_path)

        assert len(loaded) == 1
        assert loaded.handlers[0].name == 'roundtrip_test'
        assert loaded.handlers[0].priority == 42
        assert loaded.handlers[0].description == 'Test description'


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_load_dialog_registry_no_config(self):
        """Test load_dialog_registry returns empty registry when no config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a nonexistent config path
            registry = load_dialog_registry(Path(tmpdir) / "nonexistent.yaml")
            assert len(registry) == 0

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not installed")
    def test_create_default_config(self):
        """Test creating default configuration file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "dialog-handlers.yaml"
            create_default_config(config_path)

            assert config_path.exists()

            # Load and verify structure
            registry = DialogRegistry.from_yaml(config_path)
            assert len(registry) > 0

            # Check some expected handlers exist
            handler_names = [h.name for h in registry.handlers]
            assert 'save_scene' in handler_names
            assert 'api_update' in handler_names


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_dialog_match_result(self):
        """Test DialogMatchResult creation."""
        handler = DialogHandler(name="test", pattern="pattern")
        result = DialogMatchResult(
            handler=handler,
            matched_text="test text",
            matched_pattern="pattern",
        )
        assert result.handler.name == "test"
        assert result.matched_text == "test text"
        assert isinstance(result.timestamp, datetime)

    def test_dialog_action_result(self):
        """Test DialogActionResult creation."""
        result = DialogActionResult(
            success=True,
            action_type=DialogActionType.CLICK_BUTTON,
            handler_name="test",
            message="Clicked OK",
        )
        assert result.success is True
        assert result.requires_human is False
        assert result.screenshot_path is None

    def test_dialog_log_entry(self):
        """Test DialogLogEntry creation."""
        action_result = DialogActionResult(
            success=True,
            action_type=DialogActionType.IGNORE,
            handler_name="test",
            message="Ignored",
        )
        entry = DialogLogEntry(
            timestamp=datetime.now(),
            handler_name="test",
            dialog_title="Test Dialog",
            dialog_content="Content",
            action_type=DialogActionType.IGNORE,
            action_result=action_result,
        )
        assert entry.handler_name == "test"
        assert entry.dialog_title == "Test Dialog"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_match_with_none_values(self):
        """Test matching with None title and content."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'test',
                'pattern': 'test',
            }]
        })
        result = registry.match_dialog(title=None, content=None)
        assert result is None

    def test_match_with_empty_strings(self):
        """Test matching with empty strings."""
        registry = DialogRegistry.from_dict({
            'handlers': [{
                'name': 'test',
                'pattern': 'test',
            }]
        })
        result = registry.match_dialog(title="", content="")
        assert result is None

    def test_registry_repr(self):
        """Test registry string representation."""
        registry = DialogRegistry()
        assert "handlers=0" in repr(registry)
        assert "log_entries=0" in repr(registry)

    def test_special_regex_characters(self):
        """Test patterns with special regex characters."""
        handler = DialogHandler(
            name="special_chars",
            pattern=r"Error\s*\[\d+\]:\s+.*",
        )
        assert handler.matches(title="Error [123]: Something went wrong") is True
        assert handler.matches(title="Error: Simple") is False
