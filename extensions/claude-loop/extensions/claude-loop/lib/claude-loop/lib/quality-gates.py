#!/usr/bin/env python3
"""
Quality Gates for Claude-Loop (INV-009)

Automatically selects and runs quality gates based on complexity level.
Invisible intelligence: users don't configure gates, they're auto-selected.

Gate Selection by Complexity:
- Level 0-1 (quick): tests only
- Level 2 (standard): tests + lint
- Level 3 (standard+): tests + lint + type_check + security_scan
- Level 4 (enterprise): all gates + manual approval checkpoint

Usage:
    # Get gates for complexity level
    python3 quality-gates.py get <complexity_level>
    python3 quality-gates.py get 3 --json

    # Run gates for a project
    python3 quality-gates.py run <complexity_level>
    python3 quality-gates.py run 3 --verbose

    # Show gate definitions
    python3 quality-gates.py list
    python3 quality-gates.py list --json
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


class GateStatus(str, Enum):
    """Status of a quality gate check."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNED = "warned"  # Non-blocking failure


class FailureAction(str, Enum):
    """What to do when a gate fails."""
    BLOCK = "block"    # Block completion
    WARN = "warn"      # Warn but allow completion
    SKIP = "skip"      # Skip this gate entirely


@dataclass
class GateDefinition:
    """Definition of a quality gate."""
    name: str
    description: str
    enabled: bool = True
    failure_action: FailureAction = FailureAction.BLOCK
    commands: dict = field(default_factory=dict)  # language -> command
    timeout_seconds: int = 300

    def get_command(self, language: str = "python") -> Optional[str]:
        """Get the command for a specific language."""
        return self.commands.get(language) or self.commands.get("default")


@dataclass
class QualityGates:
    """Quality gates configuration for a complexity level."""
    complexity_level: int
    complexity_name: str
    tests: GateDefinition
    lint: GateDefinition
    type_check: GateDefinition
    security_scan: GateDefinition
    coverage_check: GateDefinition
    manual_approval: GateDefinition

    def get_enabled_gates(self) -> list[GateDefinition]:
        """Get list of enabled gates in execution order."""
        all_gates = [
            self.tests,
            self.lint,
            self.type_check,
            self.security_scan,
            self.coverage_check,
            self.manual_approval,
        ]
        return [g for g in all_gates if g.enabled]

    def get_blocking_gates(self) -> list[GateDefinition]:
        """Get gates that block on failure."""
        return [g for g in self.get_enabled_gates()
                if g.failure_action == FailureAction.BLOCK]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "complexity_level": self.complexity_level,
            "complexity_name": self.complexity_name,
            "gates": {
                "tests": asdict(self.tests),
                "lint": asdict(self.lint),
                "type_check": asdict(self.type_check),
                "security_scan": asdict(self.security_scan),
                "coverage_check": asdict(self.coverage_check),
                "manual_approval": asdict(self.manual_approval),
            },
            "enabled_gates": [g.name for g in self.get_enabled_gates()],
            "blocking_gates": [g.name for g in self.get_blocking_gates()],
        }


@dataclass
class GateResult:
    """Result of running a quality gate."""
    gate_name: str
    status: GateStatus
    failure_action: FailureAction
    duration_ms: int = 0
    output: str = ""
    error: str = ""
    command_run: str = ""
    exit_code: int = 0

    @property
    def passed(self) -> bool:
        return self.status in (GateStatus.PASSED, GateStatus.SKIPPED, GateStatus.WARNED)

    @property
    def blocking(self) -> bool:
        return self.status == GateStatus.FAILED and self.failure_action == FailureAction.BLOCK


@dataclass
class QualityGatesResult:
    """Result of running all quality gates."""
    complexity_level: int
    gates_run: list[GateResult]
    all_passed: bool
    blocked: bool
    blocking_failures: list[str]
    warnings: list[str]
    total_duration_ms: int

    def to_dict(self) -> dict:
        return {
            "complexity_level": self.complexity_level,
            "all_passed": self.all_passed,
            "blocked": self.blocked,
            "blocking_failures": self.blocking_failures,
            "warnings": self.warnings,
            "total_duration_ms": self.total_duration_ms,
            "gates_run": [asdict(g) for g in self.gates_run],
        }


# Gate command templates
GATE_COMMANDS = {
    "tests": {
        "python": "pytest",
        "javascript": "npm test",
        "typescript": "npm test",
        "go": "go test ./...",
        "rust": "cargo test",
        "default": "echo 'No test command configured'",
    },
    "lint": {
        "python": "ruff check . || pylint **/*.py",
        "javascript": "eslint .",
        "typescript": "eslint .",
        "go": "golangci-lint run",
        "rust": "cargo clippy",
        "default": "echo 'No lint command configured'",
    },
    "type_check": {
        "python": "pyright || mypy .",
        "typescript": "tsc --noEmit",
        "go": "go vet ./...",
        "default": "echo 'No type check command configured'",
    },
    "security_scan": {
        "python": "bandit -r . -ll || safety check",
        "javascript": "npm audit --audit-level=high",
        "typescript": "npm audit --audit-level=high",
        "general": "gitleaks detect --no-git || trufflehog filesystem .",
        "default": "echo 'No security scan configured'",
    },
    "coverage_check": {
        "python": "pytest --cov --cov-fail-under=80",
        "javascript": "npm test -- --coverage --coverageThreshold='{\"global\":{\"lines\":80}}'",
        "typescript": "npm test -- --coverage --coverageThreshold='{\"global\":{\"lines\":80}}'",
        "go": "go test -coverprofile=coverage.out ./... && go tool cover -func=coverage.out | grep total | awk '{if ($3+0 < 80) exit 1}'",
        "default": "echo 'No coverage check configured'",
    },
}

# Complexity level names
COMPLEXITY_NAMES = {
    0: "micro",
    1: "small",
    2: "medium",
    3: "large",
    4: "enterprise",
}


def create_gate(
    name: str,
    description: str,
    enabled: bool,
    failure_action: FailureAction,
    commands: Optional[dict] = None,
    timeout_seconds: int = 300,
) -> GateDefinition:
    """Create a gate definition with sensible defaults."""
    return GateDefinition(
        name=name,
        description=description,
        enabled=enabled,
        failure_action=failure_action,
        commands=commands or GATE_COMMANDS.get(name, {}),
        timeout_seconds=timeout_seconds,
    )


def get_gates(complexity: int) -> QualityGates:
    """
    Get quality gates configuration for a complexity level.

    Gate Selection:
    - Level 0-1 (quick): tests only
    - Level 2 (standard): tests + lint
    - Level 3 (standard+): tests + lint + type_check + security_scan
    - Level 4 (enterprise): all gates + manual approval checkpoint

    Args:
        complexity: Complexity level 0-4

    Returns:
        QualityGates configuration for the level
    """
    complexity = max(0, min(4, complexity))  # Clamp to 0-4
    complexity_name = COMPLEXITY_NAMES.get(complexity, "unknown")

    # Base gates - always defined, enabled status varies by complexity
    if complexity <= 1:
        # Quick track: tests only
        return QualityGates(
            complexity_level=complexity,
            complexity_name=complexity_name,
            tests=create_gate(
                "tests",
                "Run test suite",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            lint=create_gate(
                "lint",
                "Run linter for code style",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            type_check=create_gate(
                "type_check",
                "Run type checker",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            security_scan=create_gate(
                "security_scan",
                "Run security scanner",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            coverage_check=create_gate(
                "coverage_check",
                "Check test coverage threshold",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            manual_approval=create_gate(
                "manual_approval",
                "Require manual approval checkpoint",
                enabled=False,
                failure_action=FailureAction.SKIP,
                commands={},
                timeout_seconds=0,
            ),
        )

    elif complexity == 2:
        # Standard track: tests + lint
        return QualityGates(
            complexity_level=complexity,
            complexity_name=complexity_name,
            tests=create_gate(
                "tests",
                "Run test suite",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            lint=create_gate(
                "lint",
                "Run linter for code style",
                enabled=True,
                failure_action=FailureAction.WARN,  # Non-blocking for level 2
            ),
            type_check=create_gate(
                "type_check",
                "Run type checker (optional at this level)",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            security_scan=create_gate(
                "security_scan",
                "Run security scanner",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            coverage_check=create_gate(
                "coverage_check",
                "Check test coverage threshold",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            manual_approval=create_gate(
                "manual_approval",
                "Require manual approval checkpoint",
                enabled=False,
                failure_action=FailureAction.SKIP,
                commands={},
                timeout_seconds=0,
            ),
        )

    elif complexity == 3:
        # Standard+ track: tests + lint + type_check + security_scan
        return QualityGates(
            complexity_level=complexity,
            complexity_name=complexity_name,
            tests=create_gate(
                "tests",
                "Run test suite",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            lint=create_gate(
                "lint",
                "Run linter for code style",
                enabled=True,
                failure_action=FailureAction.BLOCK,  # Blocking for level 3
            ),
            type_check=create_gate(
                "type_check",
                "Run type checker",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            security_scan=create_gate(
                "security_scan",
                "Run security scanner",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            coverage_check=create_gate(
                "coverage_check",
                "Check test coverage threshold",
                enabled=False,
                failure_action=FailureAction.SKIP,
            ),
            manual_approval=create_gate(
                "manual_approval",
                "Require manual approval checkpoint",
                enabled=False,
                failure_action=FailureAction.SKIP,
                commands={},
                timeout_seconds=0,
            ),
        )

    else:
        # Enterprise track (level 4): all gates + manual approval
        return QualityGates(
            complexity_level=complexity,
            complexity_name=complexity_name,
            tests=create_gate(
                "tests",
                "Run test suite",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            lint=create_gate(
                "lint",
                "Run linter for code style",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            type_check=create_gate(
                "type_check",
                "Run type checker",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            security_scan=create_gate(
                "security_scan",
                "Run security scanner",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            coverage_check=create_gate(
                "coverage_check",
                "Check test coverage threshold (80% minimum)",
                enabled=True,
                failure_action=FailureAction.BLOCK,
            ),
            manual_approval=create_gate(
                "manual_approval",
                "Require manual approval checkpoint before completion",
                enabled=True,
                failure_action=FailureAction.BLOCK,
                commands={},  # Manual approval doesn't have a command
                timeout_seconds=0,
            ),
        )


def detect_language(project_dir: str = ".") -> str:
    """Detect the primary language of a project."""
    indicators = {
        "python": ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile"],
        "javascript": ["package.json"],
        "typescript": ["tsconfig.json"],
        "go": ["go.mod"],
        "rust": ["Cargo.toml"],
    }

    for language, files in indicators.items():
        for f in files:
            if os.path.exists(os.path.join(project_dir, f)):
                # Special case: check if it's TypeScript vs JavaScript
                if language == "javascript":
                    if os.path.exists(os.path.join(project_dir, "tsconfig.json")):
                        return "typescript"
                return language

    return "default"


def run_gate(
    gate: GateDefinition,
    language: str = "python",
    project_dir: str = ".",
    verbose: bool = False,
) -> GateResult:
    """
    Run a quality gate and return the result.

    Args:
        gate: Gate definition to run
        language: Project language for command selection
        project_dir: Project directory to run in
        verbose: Enable verbose output

    Returns:
        GateResult with status and details
    """
    import time

    if not gate.enabled:
        return GateResult(
            gate_name=gate.name,
            status=GateStatus.SKIPPED,
            failure_action=gate.failure_action,
            output="Gate disabled for this complexity level",
        )

    command = gate.get_command(language)
    if not command:
        return GateResult(
            gate_name=gate.name,
            status=GateStatus.SKIPPED,
            failure_action=gate.failure_action,
            output=f"No command configured for language: {language}",
        )

    # Special handling for manual approval
    if gate.name == "manual_approval":
        return GateResult(
            gate_name=gate.name,
            status=GateStatus.PENDING,
            failure_action=gate.failure_action,
            output="Manual approval required. Please review and approve.",
        )

    if verbose:
        print(f"  Running {gate.name}: {command}", file=sys.stderr)

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=gate.timeout_seconds,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        if result.returncode == 0:
            status = GateStatus.PASSED
        elif gate.failure_action == FailureAction.WARN:
            status = GateStatus.WARNED
        else:
            status = GateStatus.FAILED

        return GateResult(
            gate_name=gate.name,
            status=status,
            failure_action=gate.failure_action,
            duration_ms=duration_ms,
            output=result.stdout,
            error=result.stderr,
            command_run=command,
            exit_code=result.returncode,
        )

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        return GateResult(
            gate_name=gate.name,
            status=GateStatus.FAILED,
            failure_action=gate.failure_action,
            duration_ms=duration_ms,
            error=f"Command timed out after {gate.timeout_seconds}s",
            command_run=command,
            exit_code=-1,
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return GateResult(
            gate_name=gate.name,
            status=GateStatus.FAILED,
            failure_action=gate.failure_action,
            duration_ms=duration_ms,
            error=str(e),
            command_run=command,
            exit_code=-1,
        )


def run_gates(
    complexity: int,
    project_dir: str = ".",
    language: Optional[str] = None,
    verbose: bool = False,
) -> QualityGatesResult:
    """
    Run all quality gates for a complexity level.

    Args:
        complexity: Complexity level 0-4
        project_dir: Project directory to run in
        language: Override language detection
        verbose: Enable verbose output

    Returns:
        QualityGatesResult with all gate results
    """
    gates = get_gates(complexity)

    if language is None:
        language = detect_language(project_dir)

    if verbose:
        print(f"Running quality gates for complexity level {complexity} ({gates.complexity_name})", file=sys.stderr)
        print(f"Detected language: {language}", file=sys.stderr)
        print(f"Enabled gates: {[g.name for g in gates.get_enabled_gates()]}", file=sys.stderr)

    results: list[GateResult] = []
    total_duration_ms = 0
    blocking_failures: list[str] = []
    warnings: list[str] = []

    for gate in gates.get_enabled_gates():
        result = run_gate(gate, language, project_dir, verbose)
        results.append(result)
        total_duration_ms += result.duration_ms

        if result.blocking:
            blocking_failures.append(f"{gate.name}: {result.error or 'Failed'}")
        elif result.status == GateStatus.WARNED:
            warnings.append(f"{gate.name}: {result.error or 'Warning'}")

        if verbose:
            status_symbol = "✓" if result.passed else ("⚠" if result.status == GateStatus.WARNED else "✗")
            print(f"  {status_symbol} {gate.name}: {result.status.value} ({result.duration_ms}ms)", file=sys.stderr)

    all_passed = len(blocking_failures) == 0
    blocked = len(blocking_failures) > 0

    return QualityGatesResult(
        complexity_level=complexity,
        gates_run=results,
        all_passed=all_passed,
        blocked=blocked,
        blocking_failures=blocking_failures,
        warnings=warnings,
        total_duration_ms=total_duration_ms,
    )


def format_gates_summary(gates: QualityGates, verbose: bool = False) -> str:
    """Format gates configuration as human-readable summary."""
    lines = [
        f"Quality Gates for Level {gates.complexity_level} ({gates.complexity_name}):",
        "",
    ]

    enabled = gates.get_enabled_gates()
    if not enabled:
        lines.append("  No gates enabled (all checks skipped)")
    else:
        lines.append("  Enabled gates:")
        for gate in enabled:
            action = gate.failure_action.value
            lines.append(f"    • {gate.name}: {gate.description} [{action}]")

        if verbose:
            disabled = [g.name for g in [
                gates.tests, gates.lint, gates.type_check,
                gates.security_scan, gates.coverage_check, gates.manual_approval
            ] if not g.enabled]
            if disabled:
                lines.append(f"\n  Disabled: {', '.join(disabled)}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Quality gates manager for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Gate Selection by Complexity:
  Level 0-1 (quick):      tests only
  Level 2 (standard):     tests + lint (warn)
  Level 3 (standard+):    tests + lint + type_check + security_scan
  Level 4 (enterprise):   all gates + coverage + manual approval

Examples:
  quality-gates.py get 2                    # Get gates for level 2
  quality-gates.py get 3 --json             # JSON output
  quality-gates.py run 2 --verbose          # Run gates with verbose output
  quality-gates.py list                     # Show all gate definitions
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # get command
    get_parser = subparsers.add_parser("get", help="Get quality gates for a complexity level")
    get_parser.add_argument(
        "complexity",
        type=int,
        choices=[0, 1, 2, 3, 4],
        help="Complexity level (0-4)",
    )
    get_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    get_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Include detailed information",
    )

    # run command
    run_parser = subparsers.add_parser("run", help="Run quality gates for a project")
    run_parser.add_argument(
        "complexity",
        type=int,
        choices=[0, 1, 2, 3, 4],
        help="Complexity level (0-4)",
    )
    run_parser.add_argument(
        "--project-dir",
        type=str,
        default=".",
        help="Project directory (default: current)",
    )
    run_parser.add_argument(
        "--language",
        type=str,
        choices=["python", "javascript", "typescript", "go", "rust"],
        help="Override language detection",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    run_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List all quality gate definitions")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    list_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Include command details",
    )

    args = parser.parse_args()

    if args.command == "get":
        gates = get_gates(args.complexity)

        if args.json:
            print(json.dumps(gates.to_dict(), indent=2))
        else:
            print(format_gates_summary(gates, args.verbose))

    elif args.command == "run":
        result = run_gates(
            args.complexity,
            project_dir=args.project_dir,
            language=args.language,
            verbose=args.verbose,
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nQuality Gates Result for Level {result.complexity_level}:")
            print(f"  Total duration: {result.total_duration_ms}ms")
            print(f"  All passed: {'✓ Yes' if result.all_passed else '✗ No'}")

            if result.blocking_failures:
                print(f"\n  Blocking failures:")
                for f in result.blocking_failures:
                    print(f"    ✗ {f}")

            if result.warnings:
                print(f"\n  Warnings (non-blocking):")
                for w in result.warnings:
                    print(f"    ⚠ {w}")

            # Exit with appropriate code
            sys.exit(0 if result.all_passed else 1)

    elif args.command == "list":
        all_gates = {level: get_gates(level) for level in range(5)}

        if args.json:
            output = {
                f"level_{level}": gates.to_dict()
                for level, gates in all_gates.items()
            }
            print(json.dumps(output, indent=2))
        else:
            print("Quality Gate Definitions by Complexity Level:")
            print("=" * 60)
            for _level, gates in all_gates.items():
                print(f"\n{format_gates_summary(gates, args.verbose)}")
                if args.verbose:
                    print()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
