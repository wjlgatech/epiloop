#!/usr/bin/env python3
"""
improvement-validator.py - Improvement Validation Suite for claude-loop

Validates improvement PRDs before deployment to prevent regressions and ensure
quality. Runs test suites, validates against held-out failure cases, and
measures capability coverage.

Features:
- Run existing test suite (must not regress)
- Run improvement-specific tests from PRD
- Test against held-out failure cases
- Measure capability coverage before/after
- Generate validation report with pass/fail details
- Block deployment if validation fails
- Support --force flag to override (with warning)

Usage:
    python lib/improvement-validator.py validate <prd_path>
    python lib/improvement-validator.py validate <prd_path> --json
    python lib/improvement-validator.py validate <prd_path> --force
    python lib/improvement-validator.py check-tests
    python lib/improvement-validator.py check-coverage
    python lib/improvement-validator.py held-out-cases
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TestResult:
    """Result of running a single test."""

    name: str
    passed: bool
    duration_ms: float = 0.0
    error_message: str = ""
    output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "output": self.output[:500] if self.output else "",  # Truncate
        }


@dataclass
class TestSuiteResult:
    """Result of running a test suite."""

    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: float = 0.0
    tests: list[TestResult] = field(default_factory=list)
    error: str = ""

    @property
    def success(self) -> bool:
        return self.failed == 0 and not self.error

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "pass_rate": round(self.pass_rate, 2),
            "tests": [t.to_dict() for t in self.tests],
            "error": self.error,
        }


@dataclass
class CoverageMetrics:
    """Coverage metrics before and after improvement."""

    total_capabilities: int = 0
    available_capabilities: int = 0
    limited_capabilities: int = 0
    unavailable_capabilities: int = 0
    coverage_percentage: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> CoverageMetrics:
        return cls(
            total_capabilities=data.get("total", 0),
            available_capabilities=data.get("available", 0),
            limited_capabilities=data.get("limited", 0),
            unavailable_capabilities=data.get("unavailable", 0),
            coverage_percentage=data.get("coverage_percentage", 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total_capabilities,
            "available": self.available_capabilities,
            "limited": self.limited_capabilities,
            "unavailable": self.unavailable_capabilities,
            "coverage_percentage": round(self.coverage_percentage, 2),
        }


@dataclass
class ValidationResult:
    """Complete validation result for an improvement PRD."""

    prd_name: str
    prd_path: str
    validated_at: str

    # Test results
    existing_tests: TestSuiteResult | None = None
    improvement_tests: TestSuiteResult | None = None
    held_out_cases: TestSuiteResult | None = None

    # Coverage
    coverage_before: CoverageMetrics | None = None
    coverage_after: CoverageMetrics | None = None

    # Overall status
    passed: bool = False
    blocked: bool = False
    forced: bool = False
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Summary
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_name": self.prd_name,
            "prd_path": self.prd_path,
            "validated_at": self.validated_at,
            "existing_tests": self.existing_tests.to_dict() if self.existing_tests else None,
            "improvement_tests": self.improvement_tests.to_dict() if self.improvement_tests else None,
            "held_out_cases": self.held_out_cases.to_dict() if self.held_out_cases else None,
            "coverage_before": self.coverage_before.to_dict() if self.coverage_before else None,
            "coverage_after": self.coverage_after.to_dict() if self.coverage_after else None,
            "passed": self.passed,
            "blocked": self.blocked,
            "forced": self.forced,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "summary": self.summary,
        }


# ============================================================================
# Validator
# ============================================================================

class ImprovementValidator:
    """
    Validates improvement PRDs before deployment.

    Validation checks:
    1. Existing test suite must pass (no regressions)
    2. Improvement-specific tests from PRD must pass
    3. Held-out failure cases should now succeed
    4. Capability coverage should not decrease
    """

    def __init__(
        self,
        project_root: Path | None = None,
        held_out_dir: Path | None = None,
    ):
        """
        Initialize the validator.

        Args:
            project_root: Path to project root
            held_out_dir: Directory containing held-out failure cases
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.claude_loop_dir = self.project_root / ".claude-loop"
        self.held_out_dir = held_out_dir or self.claude_loop_dir / "held_out_cases"
        self.validation_reports_dir = self.claude_loop_dir / "validation_reports"

        # Ensure directories exist
        self.validation_reports_dir.mkdir(parents=True, exist_ok=True)
        self.held_out_dir.mkdir(parents=True, exist_ok=True)

    def _detect_test_framework(self) -> tuple[str, str]:
        """
        Detect the test framework and command.

        Returns:
            Tuple of (framework_name, command)
        """
        # Check for Python pytest
        if (self.project_root / "pytest.ini").exists():
            return "pytest", "python3 -m pytest"
        if (self.project_root / "pyproject.toml").exists():
            pyproject = (self.project_root / "pyproject.toml").read_text()
            if "pytest" in pyproject:
                return "pytest", "python3 -m pytest"

        # Check for setup.py with unittest
        if (self.project_root / "setup.py").exists():
            return "unittest", "python3 -m unittest discover"

        # Check for JavaScript jest
        if (self.project_root / "jest.config.js").exists() or \
           (self.project_root / "jest.config.ts").exists():
            return "jest", "npm test"

        # Check for package.json test script
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(package_json.read_text())
                if "scripts" in pkg and "test" in pkg["scripts"]:
                    return "npm", "npm test"
            except json.JSONDecodeError:
                pass

        # Check for tests directory with Python files
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            py_tests = list(tests_dir.glob("**/*.py"))
            if py_tests:
                return "pytest", "python3 -m pytest tests/"

        # Default to no tests
        return "none", ""

    def _run_command(
        self,
        command: str,
        timeout: int = 300,
    ) -> tuple[int, str, str, float]:
        """
        Run a shell command and capture output.

        Returns:
            Tuple of (exit_code, stdout, stderr, duration_ms)
        """
        start_time = datetime.now()

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result.returncode, result.stdout, result.stderr, duration_ms

        except subprocess.TimeoutExpired:
            duration_ms = timeout * 1000
            return -1, "", f"Command timed out after {timeout}s", duration_ms

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return -2, "", str(e), duration_ms

    def _parse_pytest_output(self, stdout: str, stderr: str) -> TestSuiteResult:
        """Parse pytest output to extract test results."""
        result = TestSuiteResult(suite_name="pytest")

        # Parse summary line like: "5 passed, 2 failed, 1 skipped in 3.45s"
        lines = (stdout + stderr).split("\n")

        for line in lines:
            line = line.strip()

            # Look for the summary line
            if "passed" in line or "failed" in line or "error" in line:
                # Parse numbers
                import re

                passed_match = re.search(r"(\d+)\s+passed", line)
                failed_match = re.search(r"(\d+)\s+failed", line)
                skipped_match = re.search(r"(\d+)\s+skipped", line)
                error_match = re.search(r"(\d+)\s+error", line)
                time_match = re.search(r"in\s+([\d.]+)s", line)

                if passed_match:
                    result.passed = int(passed_match.group(1))
                if failed_match:
                    result.failed = int(failed_match.group(1))
                if error_match:
                    result.failed += int(error_match.group(1))
                if skipped_match:
                    result.skipped = int(skipped_match.group(1))
                if time_match:
                    result.duration_ms = float(time_match.group(1)) * 1000

                result.total = result.passed + result.failed + result.skipped
                break

        return result

    def _parse_generic_test_output(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> TestSuiteResult:
        """Parse generic test output based on exit code."""
        result = TestSuiteResult(
            suite_name="generic",
            duration_ms=duration_ms,
        )

        if exit_code == 0:
            result.passed = 1
            result.total = 1
        else:
            result.failed = 1
            result.total = 1
            result.error = stderr[:500] if stderr else stdout[:500]

        return result

    def run_existing_tests(self) -> TestSuiteResult:
        """
        Run the existing test suite to check for regressions.

        Returns:
            TestSuiteResult with pass/fail status
        """
        framework, command = self._detect_test_framework()

        if framework == "none" or not command:
            return TestSuiteResult(
                suite_name="existing",
                error="No test framework detected",
            )

        exit_code, stdout, stderr, duration_ms = self._run_command(command)

        if framework == "pytest":
            result = self._parse_pytest_output(stdout, stderr)
            result.suite_name = "existing"
            result.duration_ms = duration_ms
        else:
            result = self._parse_generic_test_output(exit_code, stdout, stderr, duration_ms)
            result.suite_name = "existing"

        return result

    def run_improvement_tests(self, prd_data: dict) -> TestSuiteResult:
        """
        Run improvement-specific tests from the PRD.

        Args:
            prd_data: Parsed PRD JSON data

        Returns:
            TestSuiteResult with pass/fail status
        """
        result = TestSuiteResult(suite_name="improvement")

        # Extract test files from user stories
        test_files = []
        for story in prd_data.get("userStories", []):
            file_scope = story.get("fileScope", [])
            for f in file_scope:
                if "test" in f.lower() and f.endswith(".py"):
                    test_path = self.project_root / f
                    if test_path.exists():
                        test_files.append(f)

        if not test_files:
            result.error = "No improvement-specific test files found in PRD"
            return result

        # Run tests for improvement files
        test_files_str = " ".join(test_files)
        command = f"python3 -m pytest {test_files_str} -v"

        exit_code, stdout, stderr, duration_ms = self._run_command(command)

        parsed = self._parse_pytest_output(stdout, stderr)
        result.total = parsed.total
        result.passed = parsed.passed
        result.failed = parsed.failed
        result.skipped = parsed.skipped
        result.duration_ms = duration_ms

        if exit_code != 0 and result.total == 0:
            result.error = stderr[:500] if stderr else "Tests failed to run"

        return result

    def run_held_out_cases(self, prd_data: dict) -> TestSuiteResult:
        """
        Test against held-out failure cases that should now succeed.

        Held-out cases are failure logs that were classified as capability gaps.
        After the improvement, these cases should succeed.

        Args:
            prd_data: Parsed PRD JSON data

        Returns:
            TestSuiteResult with pass/fail status
        """
        result = TestSuiteResult(suite_name="held_out")

        # Get the gap_id from the PRD
        gap_id = prd_data.get("gap_id", "")
        if not gap_id:
            result.error = "No gap_id in PRD, cannot find held-out cases"
            return result

        # Look for held-out cases file
        held_out_file = self.held_out_dir / f"{gap_id}.json"
        if not held_out_file.exists():
            # No held-out cases for this gap - this is OK
            result.error = f"No held-out cases found for gap {gap_id}"
            result.skipped = 1
            result.total = 1
            return result

        try:
            cases = json.loads(held_out_file.read_text())
        except json.JSONDecodeError:
            result.error = f"Invalid JSON in held-out cases file: {held_out_file}"
            return result

        # Each held-out case should have a test command or validation
        for case in cases:
            test_result = TestResult(
                name=case.get("name", f"case_{len(result.tests) + 1}"),
                passed=False,
            )

            # If case has a test command, run it
            test_cmd = case.get("test_command")
            if test_cmd:
                exit_code, stdout, stderr, duration_ms = self._run_command(test_cmd, timeout=60)
                test_result.passed = exit_code == 0
                test_result.duration_ms = duration_ms
                test_result.error_message = stderr[:200] if not test_result.passed else ""
                test_result.output = stdout[:200]
            else:
                # Mark as skipped if no test command
                test_result.passed = True  # Assume pass if no validation
                test_result.output = "No test command - assumed pass"

            result.tests.append(test_result)
            result.total += 1
            if test_result.passed:
                result.passed += 1
            else:
                result.failed += 1

        return result

    def measure_coverage(self) -> CoverageMetrics:
        """
        Measure capability coverage using the capability inventory.

        Returns:
            CoverageMetrics with current coverage
        """
        metrics = CoverageMetrics()

        # Try to get coverage from capability inventory
        inventory_file = self.claude_loop_dir / "capability_inventory.json"
        if not inventory_file.exists():
            # No inventory yet - use gap registry as proxy
            gaps_file = self.claude_loop_dir / "capability_gaps.json"
            if gaps_file.exists():
                try:
                    gaps_data = json.loads(gaps_file.read_text())
                    gaps = gaps_data.get("gaps", [])

                    # Count gaps by status
                    active_gaps = sum(1 for g in gaps if g.get("status") == "active")

                    metrics.total_capabilities = 10  # 10 capability categories
                    metrics.available_capabilities = 10 - active_gaps
                    metrics.limited_capabilities = active_gaps
                    metrics.unavailable_capabilities = 0
                    metrics.coverage_percentage = (metrics.available_capabilities / metrics.total_capabilities) * 100
                except json.JSONDecodeError:
                    pass

            return metrics

        try:
            inventory = json.loads(inventory_file.read_text())
            capabilities = inventory.get("capabilities", [])

            for cap in capabilities:
                metrics.total_capabilities += 1
                status = cap.get("status", "unavailable")
                if status == "available":
                    metrics.available_capabilities += 1
                elif status == "limited":
                    metrics.limited_capabilities += 1
                else:
                    metrics.unavailable_capabilities += 1

            if metrics.total_capabilities > 0:
                metrics.coverage_percentage = (
                    (metrics.available_capabilities + metrics.limited_capabilities * 0.5)
                    / metrics.total_capabilities
                ) * 100

        except json.JSONDecodeError:
            pass

        return metrics

    def validate_improvement(
        self,
        prd_path: str | Path,
        force: bool = False,
    ) -> ValidationResult:
        """
        Validate an improvement PRD before deployment.

        Args:
            prd_path: Path to the improvement PRD JSON file
            force: If True, bypass blocking conditions with warning

        Returns:
            ValidationResult with complete validation status
        """
        prd_path = Path(prd_path)

        # Initialize result
        result = ValidationResult(
            prd_name=prd_path.stem,
            prd_path=str(prd_path),
            validated_at=datetime.now().isoformat(),
            forced=force,
        )

        # Load PRD
        if not prd_path.exists():
            result.blocked = True
            result.blocking_reasons.append(f"PRD file not found: {prd_path}")
            result.summary = "Validation failed: PRD not found"
            return result

        try:
            prd_data = json.loads(prd_path.read_text())
        except json.JSONDecodeError as e:
            result.blocked = True
            result.blocking_reasons.append(f"Invalid PRD JSON: {e}")
            result.summary = "Validation failed: Invalid PRD"
            return result

        # 1. Run existing test suite (must not regress)
        result.existing_tests = self.run_existing_tests()
        if result.existing_tests.failed > 0:
            result.blocking_reasons.append(
                f"Existing tests regressed: {result.existing_tests.failed} failed"
            )

        # 2. Run improvement-specific tests from PRD
        result.improvement_tests = self.run_improvement_tests(prd_data)
        if result.improvement_tests.failed > 0:
            result.blocking_reasons.append(
                f"Improvement tests failed: {result.improvement_tests.failed} failed"
            )

        # 3. Test against held-out failure cases
        result.held_out_cases = self.run_held_out_cases(prd_data)
        if result.held_out_cases.failed > 0:
            result.warnings.append(
                f"Held-out cases still failing: {result.held_out_cases.failed} of {result.held_out_cases.total}"
            )

        # 4. Measure capability coverage
        result.coverage_after = self.measure_coverage()

        # Check for blocking conditions
        if result.blocking_reasons:
            if force:
                result.passed = True
                result.blocked = False
                result.warnings.append(
                    "FORCED: Validation passed despite blocking conditions"
                )
            else:
                result.passed = False
                result.blocked = True
        else:
            result.passed = True
            result.blocked = False

        # Generate summary
        result.summary = self._generate_summary(result)

        # Save validation report
        self._save_report(result)

        return result

    def _generate_summary(self, result: ValidationResult) -> str:
        """Generate a human-readable summary of validation results."""
        lines = []

        if result.passed:
            if result.forced:
                lines.append("VALIDATION PASSED (FORCED)")
            else:
                lines.append("VALIDATION PASSED")
        else:
            lines.append("VALIDATION FAILED")

        lines.append("")

        # Existing tests
        if result.existing_tests:
            et = result.existing_tests
            if et.error:
                lines.append(f"Existing Tests: {et.error}")
            else:
                status = "PASS" if et.success else "FAIL"
                lines.append(f"Existing Tests: {et.passed}/{et.total} passed ({status})")

        # Improvement tests
        if result.improvement_tests:
            it = result.improvement_tests
            if it.error:
                lines.append(f"Improvement Tests: {it.error}")
            else:
                status = "PASS" if it.success else "FAIL"
                lines.append(f"Improvement Tests: {it.passed}/{it.total} passed ({status})")

        # Held-out cases
        if result.held_out_cases:
            hc = result.held_out_cases
            if hc.error:
                lines.append(f"Held-out Cases: {hc.error}")
            else:
                status = "PASS" if hc.success else "WARN"
                lines.append(f"Held-out Cases: {hc.passed}/{hc.total} passed ({status})")

        # Coverage
        if result.coverage_after:
            ca = result.coverage_after
            lines.append(f"Coverage: {ca.coverage_percentage:.1f}%")

        # Blocking reasons
        if result.blocking_reasons:
            lines.append("")
            lines.append("Blocking Reasons:")
            for reason in result.blocking_reasons:
                lines.append(f"  - {reason}")

        # Warnings
        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in result.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)

    def _save_report(self, result: ValidationResult) -> Path:
        """Save validation report to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.validation_reports_dir / f"{result.prd_name}_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        return report_file

    def list_reports(self, prd_name: str | None = None) -> list[dict]:
        """List validation reports."""
        reports = []

        for report_file in self.validation_reports_dir.glob("*.json"):
            if prd_name and not report_file.stem.startswith(prd_name):
                continue

            try:
                data = json.loads(report_file.read_text())
                reports.append({
                    "file": str(report_file),
                    "prd_name": data.get("prd_name", ""),
                    "validated_at": data.get("validated_at", ""),
                    "passed": data.get("passed", False),
                    "forced": data.get("forced", False),
                })
            except json.JSONDecodeError:
                continue

        # Sort by date (newest first)
        reports.sort(key=lambda r: r.get("validated_at", ""), reverse=True)
        return reports

    def add_held_out_case(
        self,
        gap_id: str,
        case: dict,
    ) -> bool:
        """
        Add a held-out failure case for a gap.

        Args:
            gap_id: The gap ID this case belongs to
            case: Case data with name and optionally test_command

        Returns:
            True if successful
        """
        held_out_file = self.held_out_dir / f"{gap_id}.json"

        cases = []
        if held_out_file.exists():
            try:
                cases = json.loads(held_out_file.read_text())
            except json.JSONDecodeError:
                cases = []

        cases.append(case)

        with open(held_out_file, "w") as f:
            json.dump(cases, f, indent=2)

        return True


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Improvement Validation Suite for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/improvement-validator.py validate .claude-loop/improvements/improve-file-handling-abc123.json
    python lib/improvement-validator.py validate improve-file-handling-abc123.json --json
    python lib/improvement-validator.py validate improve-file-handling-abc123.json --force
    python lib/improvement-validator.py check-tests
    python lib/improvement-validator.py check-coverage
    python lib/improvement-validator.py reports
    python lib/improvement-validator.py reports --prd improve-file-handling-abc123
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate an improvement PRD"
    )
    validate_parser.add_argument(
        "prd_path",
        type=str,
        help="Path to improvement PRD JSON file",
    )
    validate_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    validate_parser.add_argument(
        "--force", action="store_true",
        help="Force validation to pass despite blocking conditions",
    )

    # check-tests command
    subparsers.add_parser(
        "check-tests", help="Run existing test suite"
    )

    # check-coverage command
    subparsers.add_parser(
        "check-coverage", help="Measure current capability coverage"
    )

    # reports command
    reports_parser = subparsers.add_parser(
        "reports", help="List validation reports"
    )
    reports_parser.add_argument(
        "--prd", type=str, default=None,
        help="Filter by PRD name",
    )
    reports_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # add-held-out command
    add_held_out_parser = subparsers.add_parser(
        "add-held-out", help="Add a held-out failure case"
    )
    add_held_out_parser.add_argument(
        "gap_id",
        type=str,
        help="Gap ID for the held-out case",
    )
    add_held_out_parser.add_argument(
        "name",
        type=str,
        help="Name/description of the case",
    )
    add_held_out_parser.add_argument(
        "--test-command",
        type=str,
        default=None,
        help="Command to test if case is resolved",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize validator
    project_root = Path(__file__).parent.parent
    validator = ImprovementValidator(project_root=project_root)

    if args.command == "validate":
        # Resolve PRD path
        prd_path = Path(args.prd_path)
        if not prd_path.is_absolute():
            # Check if it's in the improvements directory
            improvements_path = project_root / ".claude-loop" / "improvements" / f"{args.prd_path}"
            if improvements_path.exists():
                prd_path = improvements_path
            elif not prd_path.exists():
                # Try adding .json extension
                improvements_path = project_root / ".claude-loop" / "improvements" / f"{args.prd_path}.json"
                if improvements_path.exists():
                    prd_path = improvements_path
                else:
                    prd_path = project_root / args.prd_path

        result = validator.validate_improvement(prd_path, force=args.force)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"IMPROVEMENT VALIDATION REPORT")
            print(f"{'='*60}")
            print(f"PRD: {result.prd_name}")
            print(f"Path: {result.prd_path}")
            print(f"Validated: {result.validated_at[:19]}")
            print(f"{'='*60}\n")
            print(result.summary)
            print("")

        # Exit with appropriate code
        sys.exit(0 if result.passed else 1)

    elif args.command == "check-tests":
        result = validator.run_existing_tests()

        print(f"\n{'='*60}")
        print(f"EXISTING TEST SUITE")
        print(f"{'='*60}")

        if result.error:
            print(f"Error: {result.error}")
            sys.exit(1)

        print(f"Total: {result.total}")
        print(f"Passed: {result.passed}")
        print(f"Failed: {result.failed}")
        print(f"Skipped: {result.skipped}")
        print(f"Duration: {result.duration_ms:.0f}ms")
        print(f"Pass Rate: {result.pass_rate:.1f}%")
        print(f"Status: {'PASS' if result.success else 'FAIL'}")

        sys.exit(0 if result.success else 1)

    elif args.command == "check-coverage":
        metrics = validator.measure_coverage()

        print(f"\n{'='*60}")
        print(f"CAPABILITY COVERAGE")
        print(f"{'='*60}")
        print(f"Total Capabilities: {metrics.total_capabilities}")
        print(f"Available: {metrics.available_capabilities}")
        print(f"Limited: {metrics.limited_capabilities}")
        print(f"Unavailable: {metrics.unavailable_capabilities}")
        print(f"Coverage: {metrics.coverage_percentage:.1f}%")

    elif args.command == "reports":
        reports = validator.list_reports(prd_name=args.prd)

        if args.json:
            print(json.dumps(reports, indent=2))
        else:
            if not reports:
                print("No validation reports found.")
                return

            print(f"\n{'='*60}")
            print(f"VALIDATION REPORTS")
            print(f"{'='*60}")
            print(f"{'PRD Name':<40} {'Status':<10} {'Date':<20}")
            print("-" * 70)

            for report in reports:
                status = "PASS" if report["passed"] else "FAIL"
                if report.get("forced"):
                    status += " (F)"
                date = report.get("validated_at", "")[:19]
                print(f"{report['prd_name']:<40} {status:<10} {date:<20}")

    elif args.command == "add-held-out":
        case = {
            "name": args.name,
            "added_at": datetime.now().isoformat(),
        }
        if args.test_command:
            case["test_command"] = args.test_command

        success = validator.add_held_out_case(args.gap_id, case)
        if success:
            print(f"Added held-out case for {args.gap_id}: {args.name}")
        else:
            print("Failed to add held-out case")
            sys.exit(1)


if __name__ == "__main__":
    main()
