#!/usr/bin/env python3
"""
TDD Enforcer - Iron Law Implementation

Ensures tests fail before implementation code is written. This is the "Iron Law" of TDD:
NO production code without a failing test first.

Usage:
    python3 lib/tdd-enforcer.py <story_id> <prd_file> [test_file]

Returns:
    0: TDD compliance verified (RED phase confirmed)
    1: TDD violation detected (test passed when it should fail, or implementation exists before test)
    2: Error or unable to verify

The Iron Law:
1. Write test first
2. Run test, verify it FAILS (RED)
3. Write minimal code to pass test (GREEN)
4. Refactor (REFACTOR)

This enforcer verifies step 2: Test must fail before implementation.
"""

import sys
import json
import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional, List


class TDDEnforcer:
    """Enforces TDD Iron Law: tests must fail before implementation."""

    def __init__(self, story_id: str, prd_file: str):
        """Initialize enforcer with story and PRD."""
        self.story_id = story_id
        self.prd_file = Path(prd_file)
        self.prd_data = self._load_prd()
        self.story = self._load_story()
        self.project_root = self.prd_file.parent.parent.parent  # prd -> active -> prds -> root

    def _load_prd(self) -> dict:
        """Load PRD from file."""
        if not self.prd_file.exists():
            raise FileNotFoundError(f"PRD file not found: {self.prd_file}")

        with open(self.prd_file) as f:
            return json.load(f)

    def _load_story(self) -> dict:
        """Load specific story from PRD."""
        for story in self.prd_data.get("userStories", []):
            if story.get("id") == self.story_id:
                return story

        raise ValueError(f"Story {self.story_id} not found in PRD")

    def _detect_test_files(self) -> List[Path]:
        """Detect test files for this story."""
        test_files = []
        file_scope = self.story.get("fileScope", [])

        for file_path in file_scope:
            # Check if it's a test file
            if "test" in file_path.lower():
                abs_path = self.project_root / file_path
                if abs_path.exists():
                    test_files.append(abs_path)

        # If no test files in file scope, search for test files
        if not test_files:
            # Search common test directories
            test_dirs = ["tests", "test", "__tests__", "spec"]
            for test_dir in test_dirs:
                test_path = self.project_root / test_dir
                if test_path.exists():
                    # Look for test files related to story
                    story_slug = self.story_id.lower().replace("-", "_")
                    for pattern in [f"test_{story_slug}*", f"*{story_slug}*test*"]:
                        test_files.extend(test_path.glob(pattern))

        return test_files

    def _detect_implementation_files(self) -> List[Path]:
        """Detect implementation files for this story."""
        impl_files = []
        file_scope = self.story.get("fileScope", [])

        for file_path in file_scope:
            # Skip test files and documentation
            if any(word in file_path.lower() for word in ["test", "doc", "readme", ".md"]):
                continue

            abs_path = self.project_root / file_path
            if abs_path.exists():
                impl_files.append(abs_path)

        return impl_files

    def _run_test(self, test_file: Path) -> Tuple[bool, str]:
        """
        Run a test file and return (passed, output).

        Returns:
            (passed, output): True if all tests passed, False if any failed
        """
        # Detect test framework and run appropriately
        if test_file.suffix == ".py":
            # Python tests (pytest, unittest)
            if self._is_pytest_test(test_file):
                return self._run_pytest(test_file)
            else:
                return self._run_unittest(test_file)
        elif test_file.suffix in [".js", ".ts", ".jsx", ".tsx"]:
            # JavaScript/TypeScript tests
            return self._run_js_test(test_file)
        elif test_file.suffix == ".sh":
            # Shell script tests
            return self._run_shell_test(test_file)
        else:
            return False, f"Unknown test file type: {test_file.suffix}"

    def _is_pytest_test(self, test_file: Path) -> bool:
        """Check if test file uses pytest."""
        with open(test_file) as f:
            content = f.read()
            return "pytest" in content or "import pytest" in content

    def _run_pytest(self, test_file: Path) -> Tuple[bool, str]:
        """Run pytest on test file."""
        try:
            result = subprocess.run(
                ["pytest", str(test_file), "-v"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=30
            )
            # pytest returns 0 if all tests pass, non-zero if any fail
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "Test timeout (30s)"
        except FileNotFoundError:
            return False, "pytest not found (install with: pip install pytest)"
        except Exception as e:
            return False, f"Error running pytest: {e}"

    def _run_unittest(self, test_file: Path) -> Tuple[bool, str]:
        """Run unittest on test file."""
        try:
            result = subprocess.run(
                ["python3", "-m", "unittest", str(test_file)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=30
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "Test timeout (30s)"
        except Exception as e:
            return False, f"Error running unittest: {e}"

    def _run_js_test(self, test_file: Path) -> Tuple[bool, str]:
        """Run JavaScript/TypeScript test."""
        # Try common JS test runners
        runners = ["npm test", "yarn test", "jest", "mocha", "vitest"]

        for runner in runners:
            try:
                result = subprocess.run(
                    runner.split() + [str(test_file)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.project_root),
                    timeout=30
                )
                passed = result.returncode == 0
                output = result.stdout + result.stderr
                return passed, output
            except FileNotFoundError:
                continue  # Try next runner
            except Exception:
                continue  # Try next runner

        return False, "No JS test runner found (npm test, jest, mocha, vitest)"

    def _run_shell_test(self, test_file: Path) -> Tuple[bool, str]:
        """Run shell script test."""
        try:
            result = subprocess.run(
                ["bash", str(test_file)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=30
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "Test timeout (30s)"
        except Exception as e:
            return False, f"Error running shell test: {e}"

    def enforce_tdd(self, test_file: Optional[str] = None) -> Tuple[bool, str, List[str]]:
        """
        Enforce TDD Iron Law.

        Args:
            test_file: Optional specific test file to check

        Returns:
            (compliant, message, violations): Tuple of compliance status, message, and violations
        """
        violations = []

        # Step 1: Check if test exists
        if test_file:
            test_files = [Path(test_file)]
        else:
            test_files = self._detect_test_files()

        if not test_files:
            violations.append("No test file found for this story")
            return False, "TDD VIOLATION: No test exists", violations

        # Step 2: Check if implementation already exists
        impl_files = self._detect_implementation_files()

        # Step 3: Run tests to verify they fail (RED phase)
        all_tests_failed = True
        test_results = []

        for test_file_path in test_files:
            passed, output = self._run_test(test_file_path)

            if passed:
                # Test passed when it should fail (RED phase violation)
                violations.append(
                    f"Test {test_file_path.name} PASSES but should FAIL (RED phase). "
                    "Test must fail before implementation."
                )
                all_tests_failed = False
            else:
                test_results.append(f"✓ {test_file_path.name} correctly FAILS (RED phase)")

        # Step 4: Check for premature implementation
        if impl_files and not all_tests_failed:
            violations.append(
                f"Implementation exists but tests pass. "
                f"This violates TDD Iron Law. Delete implementation and start over."
            )
            return False, "TDD VIOLATION: Implementation exists before failing test", violations

        # If all tests failed correctly, TDD is being followed
        if all_tests_failed and test_files:
            message = "TDD COMPLIANT: Tests fail as expected (RED phase)\n"
            message += "\n".join(test_results)
            return True, message, []

        # If some tests passed when they shouldn't
        if violations:
            return False, "TDD VIOLATION: Tests should fail before implementation", violations

        return True, "TDD compliance verified", []

    def generate_report(self, compliant: bool, message: str, violations: List[str]) -> str:
        """Generate TDD enforcement report."""
        report = []
        report.append("=" * 70)
        report.append("TDD ENFORCEMENT - IRON LAW")
        report.append("=" * 70)
        report.append("")
        report.append(f"Story: {self.story_id} - {self.story.get('title', 'N/A')}")
        report.append(f"Result: {'✅ COMPLIANT' if compliant else '❌ VIOLATION'}")
        report.append("")

        if compliant:
            report.append("✓ Tests fail as expected (RED phase)")
            report.append("✓ Ready to write minimal implementation (GREEN phase)")
            report.append("")
            report.append("Next Steps:")
            report.append("  1. Write minimal code to make tests pass")
            report.append("  2. Run tests again, verify they pass")
            report.append("  3. Refactor if needed")
        else:
            report.append("Violations Found:")
            for i, violation in enumerate(violations, 1):
                report.append(f"  {i}. {violation}")
            report.append("")
            report.append("Action Required:")
            report.append("  - Fix violations listed above")
            report.append("  - Delete implementation if it exists")
            report.append("  - Ensure tests fail first (RED phase)")
            report.append("  - Re-run TDD enforcer to verify")

        report.append("")
        report.append("The Iron Law of TDD:")
        report.append("  1. Write test first")
        report.append("  2. Run test, verify it FAILS (RED)")
        report.append("  3. Write minimal code to pass test (GREEN)")
        report.append("  4. Refactor (REFACTOR)")
        report.append("")
        report.append("=" * 70)

        return "\n".join(report)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python3 lib/tdd-enforcer.py <story_id> <prd_file> [test_file]")
        print("")
        print("Example:")
        print('  python3 lib/tdd-enforcer.py US-001 prd.json')
        print('  python3 lib/tdd-enforcer.py US-001 prd.json tests/test_session_hooks.py')
        sys.exit(1)

    story_id = sys.argv[1]
    prd_file = sys.argv[2]
    test_file = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        enforcer = TDDEnforcer(story_id, prd_file)
        compliant, message, violations = enforcer.enforce_tdd(test_file)
        report = enforcer.generate_report(compliant, message, violations)

        print(report)

        # Exit with appropriate code
        sys.exit(0 if compliant else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
