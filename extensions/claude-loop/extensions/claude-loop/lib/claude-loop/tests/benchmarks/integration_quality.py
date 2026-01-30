#!/usr/bin/env python3
"""
Integration Quality Benchmarks (US-ORG-007)

Validates that there are no conflicts, all skills are covered, routing is accurate,
and decisions are fast.

Benchmarks:
1. No-Conflict Test - verify no duplicate capabilities (target: 0 conflicts)
2. Coverage Test - verify 100% skill implementation coverage
3. Routing Accuracy Test - measure routing accuracy on 100 test requests (target: 95%+)
4. Decision Latency Test - measure decision time (target: <100ms)
"""

import sys
import json
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, UTC

# Add lib/orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib" / "orchestrator"))

from diagnosis import SituationDiagnosis
from decision_engine import DecisionEngine


@dataclass
class BenchmarkResult:
    """Result of a single benchmark"""
    name: str
    passed: bool
    target: str
    actual: str
    metric: float
    details: Dict
    timestamp: str


@dataclass
class IntegrationQualityReport:
    """Complete integration quality benchmark report"""
    benchmarks: List[BenchmarkResult]
    summary: Dict
    timestamp: str
    duration_seconds: float


class IntegrationQualityBenchmark:
    """
    Integration quality benchmark suite.

    Validates orchestrator integration quality through 4 benchmarks:
    - No conflicts in capabilities
    - 100% coverage of documented skills
    - 95%+ routing accuracy
    - <100ms decision latency
    """

    def __init__(self, project_root: Path = None):
        """
        Initialize benchmark suite.

        Args:
            project_root: Path to project root (default: auto-detect)
        """
        if project_root is None:
            # Auto-detect: 3 levels up from this file
            project_root = Path(__file__).parent.parent.parent

        self.project_root = Path(project_root)
        self.skills_dir = self.project_root / "skills"
        self.skills_overview = self.project_root / "lib" / "skills-overview.md"
        self.test_cases_file = Path(__file__).parent / "test_cases" / "routing_accuracy.yaml"

        self.diagnoser = SituationDiagnosis()
        self.engine = DecisionEngine()

    def run_all(self) -> IntegrationQualityReport:
        """
        Run all 4 benchmarks.

        Returns:
            Complete benchmark report with results and summary
        """
        start_time = time.time()
        results = []

        print("\n" + "="*60)
        print("INTEGRATION QUALITY BENCHMARKS")
        print("="*60 + "\n")

        # Benchmark 1: No-Conflict Test
        print("Running Benchmark 1: No-Conflict Test...")
        results.append(self.benchmark_no_conflicts())

        # Benchmark 2: Coverage Test
        print("Running Benchmark 2: Coverage Test...")
        results.append(self.benchmark_coverage())

        # Benchmark 3: Routing Accuracy Test
        print("Running Benchmark 3: Routing Accuracy Test...")
        results.append(self.benchmark_routing_accuracy())

        # Benchmark 4: Decision Latency Test
        print("Running Benchmark 4: Decision Latency Test...")
        results.append(self.benchmark_decision_latency())

        duration = time.time() - start_time

        # Generate summary
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        overall_passed = passed_count == total_count

        summary = {
            "total_benchmarks": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "pass_rate": passed_count / total_count,
            "overall_passed": overall_passed
        }

        report = IntegrationQualityReport(
            benchmarks=results,
            summary=summary,
            timestamp=datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
            duration_seconds=duration
        )

        # Print summary
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        print(f"Total: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_count - passed_count}")
        print(f"Pass Rate: {summary['pass_rate']*100:.1f}%")
        print(f"Duration: {duration:.2f}s")
        print(f"Overall: {'✅ PASSED' if overall_passed else '❌ FAILED'}")
        print("="*60 + "\n")

        return report

    def benchmark_no_conflicts(self) -> BenchmarkResult:
        """
        Benchmark 1: No-Conflict Test

        Scan all skills/agents/workflows and verify no duplicate capabilities.
        Target: 0 conflicts

        Returns:
            BenchmarkResult with conflict count and details
        """
        conflicts = []
        capabilities = {}  # capability -> list of components

        # Scan skills
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill_name = skill_dir.name
                    skill_file = skill_dir / "SKILL.md"

                    # Read skill file to extract capabilities
                    with open(skill_file, "r") as f:
                        content = f.read().lower()

                        # Extract keywords/capabilities from "When:" section
                        if "when:" in content or "**when**" in content:
                            # Simple capability extraction: look for keywords
                            keywords = set()
                            if "api" in content:
                                keywords.add("api")
                            if "test" in content:
                                keywords.add("testing")
                            if "prd" in content:
                                keywords.add("prd")
                            if "commit" in content:
                                keywords.add("commit")
                            if "cost" in content:
                                keywords.add("optimization")
                            if "brainstorm" in content:
                                keywords.add("planning")

                            for keyword in keywords:
                                if keyword not in capabilities:
                                    capabilities[keyword] = []
                                capabilities[keyword].append(f"skill:{skill_name}")

        # Check for conflicts (same capability in multiple components)
        for capability, components in capabilities.items():
            if len(components) > 1:
                conflicts.append({
                    "capability": capability,
                    "components": components,
                    "count": len(components)
                })

        conflict_count = len(conflicts)
        passed = conflict_count == 0

        result = BenchmarkResult(
            name="No-Conflict Test",
            passed=passed,
            target="0 conflicts",
            actual=f"{conflict_count} conflicts",
            metric=float(conflict_count),
            details={
                "conflicts": conflicts,
                "capabilities_scanned": len(capabilities),
                "components_scanned": sum(len(comps) for comps in capabilities.values())
            },
            timestamp=datetime.now(UTC).isoformat().replace('+00:00', 'Z')
        )

        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status} - {conflict_count} conflicts (target: 0)")

        return result

    def benchmark_coverage(self) -> BenchmarkResult:
        """
        Benchmark 2: Coverage Test

        Verify every skill in skills-overview.md has SKILL.md implementation.
        Target: 100% coverage

        Returns:
            BenchmarkResult with coverage percentage and missing skills
        """
        documented_skills = []
        implemented_skills = []
        missing_skills = []

        # Read skills-overview.md to get documented skills
        if self.skills_overview.exists():
            with open(self.skills_overview, "r") as f:
                content = f.read()

                # Extract skill names from "**skill-name**" format
                in_available_section = False
                for line in content.split("\n"):
                    if "## Available Skills (Implemented)" in line:
                        in_available_section = True
                        continue

                    if in_available_section:
                        if line.startswith("## "):
                            # End of Available Skills section
                            break

                        if line.startswith("**") and "**" in line[2:]:
                            # Extract skill name from **skill-name**
                            skill_name = line.split("**")[1]
                            documented_skills.append(skill_name)

        # Get implemented skills
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    implemented_skills.append(skill_dir.name)

        # Check for missing implementations
        for skill in documented_skills:
            if skill not in implemented_skills:
                missing_skills.append(skill)

        total_documented = len(documented_skills)
        total_implemented = len(implemented_skills)
        coverage = (total_documented - len(missing_skills)) / total_documented if total_documented > 0 else 1.0

        passed = coverage == 1.0

        result = BenchmarkResult(
            name="Coverage Test",
            passed=passed,
            target="100% coverage",
            actual=f"{coverage*100:.1f}% coverage",
            metric=coverage,
            details={
                "documented_skills": documented_skills,
                "implemented_skills": implemented_skills,
                "missing_skills": missing_skills,
                "coverage_count": f"{total_documented - len(missing_skills)}/{total_documented}"
            },
            timestamp=datetime.now(UTC).isoformat().replace('+00:00', 'Z')
        )

        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status} - {coverage*100:.1f}% coverage (target: 100%)")
        if missing_skills:
            print(f"    Missing: {', '.join(missing_skills)}")

        return result

    def benchmark_routing_accuracy(self) -> BenchmarkResult:
        """
        Benchmark 3: Routing Accuracy Test

        Measure routing accuracy on 100 test requests with known correct routing.
        Target: 95%+ accuracy

        Returns:
            BenchmarkResult with accuracy percentage and details
        """
        # Load test cases
        if not self.test_cases_file.exists():
            # Create default test cases if file doesn't exist
            self._create_default_test_cases()

        with open(self.test_cases_file, "r") as f:
            test_cases = yaml.safe_load(f)

        correct_count = 0
        incorrect_count = 0
        errors = []

        for i, test_case in enumerate(test_cases.get("test_cases", [])):
            request = test_case["request"]
            expected_components = set(test_case["expected_routing"])

            try:
                # Run diagnosis and decision
                diagnosis = self.diagnoser.diagnose(request)
                decisions = self.engine.decide(diagnosis)

                # Get actual routed components
                actual_components = set(decisions.execution_order)

                # Check if routing is correct
                if actual_components == expected_components:
                    correct_count += 1
                else:
                    incorrect_count += 1
                    errors.append({
                        "test_case": i + 1,
                        "request": request,
                        "expected": list(expected_components),
                        "actual": list(actual_components)
                    })

            except Exception as e:
                incorrect_count += 1
                errors.append({
                    "test_case": i + 1,
                    "request": request,
                    "error": str(e)
                })

        total_count = correct_count + incorrect_count
        accuracy = correct_count / total_count if total_count > 0 else 0.0

        passed = accuracy >= 0.95

        result = BenchmarkResult(
            name="Routing Accuracy Test",
            passed=passed,
            target="95%+ accuracy",
            actual=f"{accuracy*100:.1f}% accuracy",
            metric=accuracy,
            details={
                "total_tests": total_count,
                "correct": correct_count,
                "incorrect": incorrect_count,
                "errors": errors[:10]  # Show first 10 errors
            },
            timestamp=datetime.now(UTC).isoformat().replace('+00:00', 'Z')
        )

        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status} - {accuracy*100:.1f}% accuracy (target: 95%)")
        print(f"    {correct_count}/{total_count} correct")

        return result

    def benchmark_decision_latency(self) -> BenchmarkResult:
        """
        Benchmark 4: Decision Latency Test

        Measure orchestrator decision time for typical requests.
        Target: <100ms average

        Returns:
            BenchmarkResult with average latency and percentiles
        """
        test_requests = [
            "build authentication feature",
            "fix bug in user profile",
            "create API for user management",
            "optimize database queries",
            "add security audit to deployment",
            "refactor payment processing",
            "implement search functionality",
            "debug production issue",
            "write tests for authentication",
            "document API endpoints"
        ]

        latencies = []

        for request in test_requests:
            start = time.time()

            # Run diagnosis and decision
            diagnosis = self.diagnoser.diagnose(request)
            decisions = self.engine.decide(diagnosis)

            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]

        passed = avg_latency < 100.0

        result = BenchmarkResult(
            name="Decision Latency Test",
            passed=passed,
            target="<100ms average",
            actual=f"{avg_latency:.1f}ms average",
            metric=avg_latency,
            details={
                "avg_ms": avg_latency,
                "min_ms": min_latency,
                "max_ms": max_latency,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
                "test_count": len(test_requests)
            },
            timestamp=datetime.now(UTC).isoformat().replace('+00:00', 'Z')
        )

        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status} - {avg_latency:.1f}ms average (target: <100ms)")
        print(f"    p50: {p50:.1f}ms, p95: {p95:.1f}ms, p99: {p99:.1f}ms")

        return result

    def _create_default_test_cases(self):
        """Create default routing accuracy test cases"""
        default_test_cases = {
            "description": "Routing accuracy test cases for orchestrator benchmarking",
            "version": "1.0",
            "test_cases": [
                {
                    "request": "build authentication feature with JWT",
                    "expected_routing": ["skill:brainstorming"]
                },
                {
                    "request": "fix typo in README",
                    "expected_routing": []
                },
                {
                    "request": "create REST API for user management",
                    "expected_routing": ["skill:brainstorming", "skill:api-spec-generator"]
                },
                {
                    "request": "optimize slow database queries",
                    "expected_routing": ["skill:brainstorming"]
                },
                {
                    "request": "write tests for payment processing",
                    "expected_routing": ["skill:test-scaffolder"]
                }
            ]
        }

        # Create test cases directory if needed
        self.test_cases_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.test_cases_file, "w") as f:
            yaml.dump(default_test_cases, f, default_flow_style=False, sort_keys=False)

    def save_report(self, report: IntegrationQualityReport, output_file: Path):
        """
        Save benchmark report to JSON file.

        Args:
            report: Benchmark report to save
            output_file: Path to output JSON file
        """
        # Convert to dict
        report_dict = {
            "benchmarks": [asdict(b) for b in report.benchmarks],
            "summary": report.summary,
            "timestamp": report.timestamp,
            "duration_seconds": report.duration_seconds
        }

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save to file
        with open(output_file, "w") as f:
            json.dump(report_dict, f, indent=2)

        print(f"Report saved to: {output_file}")


def main():
    """CLI interface"""
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Integration Quality Benchmarks (US-ORG-007)")
    parser.add_argument("--report", help="Output report file (JSON)", default="benchmarks/integration-quality-report.json")
    parser.add_argument("--project-root", help="Project root directory", default=None)

    args = parser.parse_args()

    # Create benchmark suite
    benchmark = IntegrationQualityBenchmark(
        project_root=Path(args.project_root) if args.project_root else None
    )

    # Run all benchmarks
    report = benchmark.run_all()

    # Save report
    report_path = Path(args.report)
    benchmark.save_report(report, report_path)

    # Exit with appropriate code
    sys.exit(0 if report.summary["overall_passed"] else 1)


if __name__ == "__main__":
    main()
