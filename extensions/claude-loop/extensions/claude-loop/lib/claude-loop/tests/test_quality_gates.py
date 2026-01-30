#!/usr/bin/env python3
"""
Unit tests for quality-gates.py (INV-009)

Tests the quality gates functionality:
- Gate selection by complexity level
- Gate definitions and properties
- Gate running and results
- Edge cases and error handling
"""

import json
import os
import sys
import tempfile
import pytest

# Add lib directory to path for imports
LIB_DIR = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.insert(0, LIB_DIR)

# Import with hyphenated module name workaround
import importlib.util
spec = importlib.util.spec_from_file_location("quality_gates", os.path.join(LIB_DIR, "quality-gates.py"))
quality_gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality_gates)

# Extract what we need from the module
get_gates = quality_gates.get_gates
detect_language = quality_gates.detect_language
run_gate = quality_gates.run_gate
run_gates = quality_gates.run_gates
format_gates_summary = quality_gates.format_gates_summary
GateStatus = quality_gates.GateStatus
FailureAction = quality_gates.FailureAction
GateDefinition = quality_gates.GateDefinition
QualityGates = quality_gates.QualityGates
GateResult = quality_gates.GateResult
QualityGatesResult = quality_gates.QualityGatesResult
COMPLEXITY_NAMES = quality_gates.COMPLEXITY_NAMES
GATE_COMMANDS = quality_gates.GATE_COMMANDS


class TestGetGates:
    """Test get_gates function for different complexity levels."""

    def test_level_0_micro_gates(self):
        """Level 0 (micro) should have tests only."""
        gates = get_gates(0)
        assert gates.complexity_level == 0
        assert gates.complexity_name == "micro"
        assert gates.tests.enabled is True
        assert gates.lint.enabled is False
        assert gates.type_check.enabled is False
        assert gates.security_scan.enabled is False
        assert gates.coverage_check.enabled is False
        assert gates.manual_approval.enabled is False

    def test_level_1_small_gates(self):
        """Level 1 (small) should have tests only."""
        gates = get_gates(1)
        assert gates.complexity_level == 1
        assert gates.complexity_name == "small"
        assert gates.tests.enabled is True
        assert gates.lint.enabled is False
        assert gates.type_check.enabled is False
        assert gates.security_scan.enabled is False
        assert gates.coverage_check.enabled is False
        assert gates.manual_approval.enabled is False

    def test_level_2_medium_gates(self):
        """Level 2 (medium/standard) should have tests + lint (warn)."""
        gates = get_gates(2)
        assert gates.complexity_level == 2
        assert gates.complexity_name == "medium"
        assert gates.tests.enabled is True
        assert gates.lint.enabled is True
        assert gates.lint.failure_action == FailureAction.WARN  # Non-blocking
        assert gates.type_check.enabled is False
        assert gates.security_scan.enabled is False
        assert gates.coverage_check.enabled is False
        assert gates.manual_approval.enabled is False

    def test_level_3_large_gates(self):
        """Level 3 (large/standard+) should have tests + lint + type_check + security_scan."""
        gates = get_gates(3)
        assert gates.complexity_level == 3
        assert gates.complexity_name == "large"
        assert gates.tests.enabled is True
        assert gates.tests.failure_action == FailureAction.BLOCK
        assert gates.lint.enabled is True
        assert gates.lint.failure_action == FailureAction.BLOCK
        assert gates.type_check.enabled is True
        assert gates.type_check.failure_action == FailureAction.BLOCK
        assert gates.security_scan.enabled is True
        assert gates.security_scan.failure_action == FailureAction.BLOCK
        assert gates.coverage_check.enabled is False
        assert gates.manual_approval.enabled is False

    def test_level_4_enterprise_gates(self):
        """Level 4 (enterprise) should have all gates + manual approval."""
        gates = get_gates(4)
        assert gates.complexity_level == 4
        assert gates.complexity_name == "enterprise"
        assert gates.tests.enabled is True
        assert gates.lint.enabled is True
        assert gates.type_check.enabled is True
        assert gates.security_scan.enabled is True
        assert gates.coverage_check.enabled is True
        assert gates.manual_approval.enabled is True
        # All should be blocking
        assert gates.tests.failure_action == FailureAction.BLOCK
        assert gates.lint.failure_action == FailureAction.BLOCK
        assert gates.type_check.failure_action == FailureAction.BLOCK
        assert gates.security_scan.failure_action == FailureAction.BLOCK
        assert gates.coverage_check.failure_action == FailureAction.BLOCK
        assert gates.manual_approval.failure_action == FailureAction.BLOCK

    def test_complexity_clamping_low(self):
        """Complexity levels below 0 should clamp to 0."""
        gates = get_gates(-1)
        assert gates.complexity_level == 0
        gates = get_gates(-100)
        assert gates.complexity_level == 0

    def test_complexity_clamping_high(self):
        """Complexity levels above 4 should clamp to 4."""
        gates = get_gates(5)
        assert gates.complexity_level == 4
        gates = get_gates(100)
        assert gates.complexity_level == 4


class TestGetEnabledGates:
    """Test get_enabled_gates method."""

    def test_level_0_enabled_gates(self):
        """Level 0 should have only tests enabled."""
        gates = get_gates(0)
        enabled = gates.get_enabled_gates()
        assert len(enabled) == 1
        assert enabled[0].name == "tests"

    def test_level_2_enabled_gates(self):
        """Level 2 should have tests and lint enabled."""
        gates = get_gates(2)
        enabled = gates.get_enabled_gates()
        assert len(enabled) == 2
        names = [g.name for g in enabled]
        assert "tests" in names
        assert "lint" in names

    def test_level_3_enabled_gates(self):
        """Level 3 should have tests, lint, type_check, security_scan enabled."""
        gates = get_gates(3)
        enabled = gates.get_enabled_gates()
        assert len(enabled) == 4
        names = [g.name for g in enabled]
        assert "tests" in names
        assert "lint" in names
        assert "type_check" in names
        assert "security_scan" in names

    def test_level_4_enabled_gates(self):
        """Level 4 should have all gates enabled."""
        gates = get_gates(4)
        enabled = gates.get_enabled_gates()
        assert len(enabled) == 6
        names = [g.name for g in enabled]
        assert "tests" in names
        assert "lint" in names
        assert "type_check" in names
        assert "security_scan" in names
        assert "coverage_check" in names
        assert "manual_approval" in names


class TestGetBlockingGates:
    """Test get_blocking_gates method."""

    def test_level_0_blocking_gates(self):
        """Level 0 should have tests as blocking."""
        gates = get_gates(0)
        blocking = gates.get_blocking_gates()
        assert len(blocking) == 1
        assert blocking[0].name == "tests"

    def test_level_2_blocking_gates(self):
        """Level 2 should have only tests as blocking (lint is warn)."""
        gates = get_gates(2)
        blocking = gates.get_blocking_gates()
        assert len(blocking) == 1
        assert blocking[0].name == "tests"

    def test_level_3_blocking_gates(self):
        """Level 3 should have all enabled gates as blocking."""
        gates = get_gates(3)
        blocking = gates.get_blocking_gates()
        assert len(blocking) == 4

    def test_level_4_blocking_gates(self):
        """Level 4 should have all gates as blocking."""
        gates = get_gates(4)
        blocking = gates.get_blocking_gates()
        assert len(blocking) == 6


class TestGateDefinition:
    """Test GateDefinition class."""

    def test_gate_get_command_python(self):
        """Test getting command for Python language."""
        gate = GateDefinition(
            name="tests",
            description="Run tests",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"python": "pytest", "javascript": "npm test"},
        )
        assert gate.get_command("python") == "pytest"
        assert gate.get_command("javascript") == "npm test"

    def test_gate_get_command_default(self):
        """Test getting default command when language not found."""
        gate = GateDefinition(
            name="tests",
            description="Run tests",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"python": "pytest", "default": "echo 'no command'"},
        )
        assert gate.get_command("go") == "echo 'no command'"

    def test_gate_get_command_none(self):
        """Test getting command when no match."""
        gate = GateDefinition(
            name="tests",
            description="Run tests",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"python": "pytest"},
        )
        assert gate.get_command("go") is None


class TestDetectLanguage:
    """Test language detection."""

    def test_detect_python_pyproject(self):
        """Test Python detection via pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "pyproject.toml"), 'w').close()
            assert detect_language(tmpdir) == "python"

    def test_detect_python_setup_py(self):
        """Test Python detection via setup.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "setup.py"), 'w').close()
            assert detect_language(tmpdir) == "python"

    def test_detect_python_requirements(self):
        """Test Python detection via requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "requirements.txt"), 'w').close()
            assert detect_language(tmpdir) == "python"

    def test_detect_javascript(self):
        """Test JavaScript detection via package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "package.json"), 'w').close()
            assert detect_language(tmpdir) == "javascript"

    def test_detect_typescript(self):
        """Test TypeScript detection via tsconfig.json + package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "package.json"), 'w').close()
            open(os.path.join(tmpdir, "tsconfig.json"), 'w').close()
            assert detect_language(tmpdir) == "typescript"

    def test_detect_go(self):
        """Test Go detection via go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "go.mod"), 'w').close()
            assert detect_language(tmpdir) == "go"

    def test_detect_rust(self):
        """Test Rust detection via Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "Cargo.toml"), 'w').close()
            assert detect_language(tmpdir) == "rust"

    def test_detect_default(self):
        """Test default when no language files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert detect_language(tmpdir) == "default"


class TestGateResult:
    """Test GateResult class."""

    def test_passed_when_status_passed(self):
        """Test passed property when status is PASSED."""
        result = GateResult(
            gate_name="tests",
            status=GateStatus.PASSED,
            failure_action=FailureAction.BLOCK,
        )
        assert result.passed is True

    def test_passed_when_status_skipped(self):
        """Test passed property when status is SKIPPED."""
        result = GateResult(
            gate_name="tests",
            status=GateStatus.SKIPPED,
            failure_action=FailureAction.BLOCK,
        )
        assert result.passed is True

    def test_passed_when_status_warned(self):
        """Test passed property when status is WARNED."""
        result = GateResult(
            gate_name="lint",
            status=GateStatus.WARNED,
            failure_action=FailureAction.WARN,
        )
        assert result.passed is True

    def test_not_passed_when_status_failed(self):
        """Test passed property when status is FAILED."""
        result = GateResult(
            gate_name="tests",
            status=GateStatus.FAILED,
            failure_action=FailureAction.BLOCK,
        )
        assert result.passed is False

    def test_blocking_when_failed_and_block_action(self):
        """Test blocking property when failed with BLOCK action."""
        result = GateResult(
            gate_name="tests",
            status=GateStatus.FAILED,
            failure_action=FailureAction.BLOCK,
        )
        assert result.blocking is True

    def test_not_blocking_when_failed_and_warn_action(self):
        """Test blocking property when failed with WARN action."""
        result = GateResult(
            gate_name="lint",
            status=GateStatus.FAILED,
            failure_action=FailureAction.WARN,
        )
        assert result.blocking is False


class TestRunGate:
    """Test run_gate function."""

    def test_run_disabled_gate(self):
        """Test running a disabled gate returns SKIPPED."""
        gate = GateDefinition(
            name="tests",
            description="Run tests",
            enabled=False,
            failure_action=FailureAction.SKIP,
            commands={"python": "pytest"},
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.SKIPPED
        assert "disabled" in result.output.lower()

    def test_run_gate_no_command(self):
        """Test running a gate with no command for language returns SKIPPED."""
        gate = GateDefinition(
            name="tests",
            description="Run tests",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={},  # No commands
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.SKIPPED
        assert "no command" in result.output.lower()

    def test_run_manual_approval_gate(self):
        """Test running manual approval gate returns PENDING.

        Note: The run_gate function has special handling for manual_approval
        gates that checks the gate name before checking for a command.
        """
        # Use a gate with the special 'manual_approval' name and a placeholder command
        gate = GateDefinition(
            name="manual_approval",
            description="Manual approval required",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"default": "true"},  # Need a command to pass the no-command check
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.PENDING
        assert "manual approval" in result.output.lower()

    def test_run_gate_success(self):
        """Test running a gate that succeeds."""
        gate = GateDefinition(
            name="echo_test",
            description="Echo test",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"default": "echo 'hello'"},
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.PASSED
        assert result.exit_code == 0

    def test_run_gate_failure_block(self):
        """Test running a gate that fails with BLOCK action."""
        gate = GateDefinition(
            name="false_test",
            description="False test",
            enabled=True,
            failure_action=FailureAction.BLOCK,
            commands={"default": "false"},  # Always exits 1
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.FAILED
        assert result.exit_code != 0
        assert result.blocking is True

    def test_run_gate_failure_warn(self):
        """Test running a gate that fails with WARN action."""
        gate = GateDefinition(
            name="false_test",
            description="False test",
            enabled=True,
            failure_action=FailureAction.WARN,
            commands={"default": "false"},  # Always exits 1
        )
        result = run_gate(gate, "python", ".")
        assert result.status == GateStatus.WARNED
        assert result.exit_code != 0
        assert result.blocking is False


class TestQualityGatesToDict:
    """Test QualityGates.to_dict method."""

    def test_to_dict_has_required_keys(self):
        """Test that to_dict returns required keys."""
        gates = get_gates(2)
        d = gates.to_dict()
        assert "complexity_level" in d
        assert "complexity_name" in d
        assert "gates" in d
        assert "enabled_gates" in d
        assert "blocking_gates" in d

    def test_to_dict_gates_structure(self):
        """Test that gates dict has correct structure."""
        gates = get_gates(3)
        d = gates.to_dict()
        assert "tests" in d["gates"]
        assert "lint" in d["gates"]
        assert "type_check" in d["gates"]
        assert "security_scan" in d["gates"]
        assert "coverage_check" in d["gates"]
        assert "manual_approval" in d["gates"]

    def test_to_dict_enabled_gates_list(self):
        """Test that enabled_gates is a list of gate names."""
        gates = get_gates(3)
        d = gates.to_dict()
        assert isinstance(d["enabled_gates"], list)
        assert "tests" in d["enabled_gates"]
        assert "lint" in d["enabled_gates"]


class TestFormatGatesSummary:
    """Test format_gates_summary function."""

    def test_format_summary_contains_level(self):
        """Test that summary contains complexity level."""
        gates = get_gates(3)
        summary = format_gates_summary(gates)
        assert "Level 3" in summary
        assert "large" in summary

    def test_format_summary_contains_enabled_gates(self):
        """Test that summary lists enabled gates."""
        gates = get_gates(3)
        summary = format_gates_summary(gates)
        assert "tests" in summary.lower()
        assert "lint" in summary.lower()

    def test_format_summary_verbose_shows_disabled(self):
        """Test that verbose summary shows disabled gates."""
        gates = get_gates(2)
        summary = format_gates_summary(gates, verbose=True)
        assert "Disabled" in summary


class TestComplexityNames:
    """Test complexity name constants."""

    def test_all_levels_have_names(self):
        """Test that all complexity levels have names."""
        for level in range(5):
            assert level in COMPLEXITY_NAMES
            assert isinstance(COMPLEXITY_NAMES[level], str)

    def test_expected_names(self):
        """Test expected complexity level names."""
        assert COMPLEXITY_NAMES[0] == "micro"
        assert COMPLEXITY_NAMES[1] == "small"
        assert COMPLEXITY_NAMES[2] == "medium"
        assert COMPLEXITY_NAMES[3] == "large"
        assert COMPLEXITY_NAMES[4] == "enterprise"


class TestGateCommands:
    """Test gate command templates."""

    def test_tests_commands_exist(self):
        """Test that tests commands exist for common languages."""
        assert "python" in GATE_COMMANDS["tests"]
        assert "javascript" in GATE_COMMANDS["tests"]
        assert "go" in GATE_COMMANDS["tests"]

    def test_lint_commands_exist(self):
        """Test that lint commands exist for common languages."""
        assert "python" in GATE_COMMANDS["lint"]
        assert "javascript" in GATE_COMMANDS["lint"]

    def test_type_check_commands_exist(self):
        """Test that type_check commands exist for common languages."""
        assert "python" in GATE_COMMANDS["type_check"]
        assert "typescript" in GATE_COMMANDS["type_check"]

    def test_security_scan_commands_exist(self):
        """Test that security_scan commands exist."""
        assert "python" in GATE_COMMANDS["security_scan"]
        assert "general" in GATE_COMMANDS["security_scan"]


class TestQualityGatesResult:
    """Test QualityGatesResult class."""

    def test_result_to_dict(self):
        """Test that QualityGatesResult.to_dict works."""
        result = QualityGatesResult(
            complexity_level=3,
            gates_run=[],
            all_passed=True,
            blocked=False,
            blocking_failures=[],
            warnings=[],
            total_duration_ms=100,
        )
        d = result.to_dict()
        assert d["complexity_level"] == 3
        assert d["all_passed"] is True
        assert d["blocked"] is False
        assert d["total_duration_ms"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
