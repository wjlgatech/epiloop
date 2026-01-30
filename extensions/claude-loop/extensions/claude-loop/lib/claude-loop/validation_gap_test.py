#!/usr/bin/env python3
"""
Validation Gap Test Suite

Tests Priority 1 fixes that prevent validation gaps where Claude implements
correctly (score ≥0.80) but forgets to set passes:true in prd.json.

Usage:
    python3 validation_gap_test.py --baseline    # Test without Priority 1 fixes
    python3 validation_gap_test.py --with-fixes  # Test with Priority 1 fixes
    python3 validation_gap_test.py --compare     # Compare baseline vs fixes
"""

import os
import sys
import json
import time
import yaml
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# Paths
BENCHMARK_DIR = Path("/Users/jialiang.wu/Documents/Projects/benchmark-tasks")
CLAUDE_LOOP_DIR = Path("/Users/jialiang.wu/Documents/Projects/claude-loop")
RESULTS_DIR = BENCHMARK_DIR / "validation_gap_results"


@dataclass
class ValidationGapResult:
    """Results from a validation gap test case"""
    task_id: str
    run_number: int
    mode: str  # "baseline" or "with_fixes"

    # Implementation quality
    criteria_score: float  # 0.0-1.0, weighted score of acceptance criteria
    criteria_passed: Dict[str, bool]

    # Validation gap detection
    passes_field_set: bool  # Did Claude set passes:true in PRD?
    validation_gap: bool  # True if score ≥0.80 but passes:false

    # Timing
    duration_seconds: float
    timestamp: str

    # Details
    error_message: Optional[str] = None
    notes: str = ""


class ValidationGapTester:
    """Test suite for validation gap detection and prevention"""

    def __init__(self, mode: str = "with_fixes"):
        """
        Initialize tester.

        Args:
            mode: "baseline" (no fixes) or "with_fixes" (Priority 1 enabled)
        """
        self.mode = mode
        self.results: List[ValidationGapResult] = []

        # Create results directory
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # Load VGAP test cases
        self.test_cases = self._load_test_cases()

        print(f"\n{'='*70}")
        print(f"VALIDATION GAP TEST SUITE - Mode: {mode.upper()}")
        print(f"{'='*70}")
        print(f"Test cases: {len(self.test_cases)}")
        print(f"Mode: {mode}")
        print(f"Results dir: {RESULTS_DIR}\n")

    def _load_test_cases(self) -> List[Dict]:
        """Load VGAP-*.yaml test case files"""
        test_cases = []
        for test_file in sorted(BENCHMARK_DIR.glob("VGAP-*.yaml")):
            with open(test_file, 'r') as f:
                task = yaml.safe_load(f)
                test_cases.append(task)
        return test_cases

    def run_tests(self, runs_per_case: int = 3):
        """
        Run all validation gap test cases.

        Args:
            runs_per_case: Number of times to run each test case
        """
        print(f"Running {len(self.test_cases)} test cases × {runs_per_case} runs = {len(self.test_cases) * runs_per_case} total\n")

        for task in self.test_cases:
            print(f"\n{'='*70}")
            print(f"TEST CASE: {task['id']} - {task['name']}")
            print(f"Purpose: {task.get('validation_gap_test', {}).get('purpose', 'N/A')}")
            print(f"{'='*70}\n")

            for run_num in range(1, runs_per_case + 1):
                print(f"  Run {run_num}/{runs_per_case}...", end=" ", flush=True)
                result = self._run_test_case(task, run_num)
                self.results.append(result)
                self._print_result(result)
                self._save_result(result)

        # Generate report
        self._generate_report()

    def _run_test_case(self, task: Dict, run_number: int) -> ValidationGapResult:
        """Run a single test case"""
        start_time = time.time()

        try:
            # Create temporary workspace
            workspace = Path(f"/tmp/vgap_test_{task['id']}_{run_number}_{int(time.time())}")
            workspace.mkdir(parents=True, exist_ok=True)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "VGAP-Test"], cwd=workspace, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "vgap@test.local"], cwd=workspace, capture_output=True, check=True)

            # Create PRD from test case
            prd_data = self._create_prd(task)
            prd_file = workspace / "prd.json"
            with open(prd_file, 'w') as f:
                json.dump(prd_data, f, indent=2)

            # Initial commit
            subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, capture_output=True, check=True)

            # Build claude-loop command
            cmd = [
                str(CLAUDE_LOOP_DIR / "claude-loop.sh"),
                "--prd", str(prd_file),
                "-m", "3",  # Max 3 iterations for simple tasks
                "--no-dashboard",
                "--no-progress",
            ]

            # BASELINE MODE: Disable Priority 1 fixes
            if self.mode == "baseline":
                # Run on older commit before Priority 1 fixes
                # OR disable features via flags (if available)
                cmd.extend([
                    "--no-auto-pass",  # Disable auto-pass logic (if flag exists)
                ])

            # WITH FIXES MODE: Enable all Priority 1 fixes (default)
            # Fixes are enabled by default in current claude-loop

            # Execute
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            duration = time.time() - start_time

            # Parse final PRD state
            with open(prd_file) as f:
                final_prd = json.load(f)

            story = final_prd['userStories'][0]
            passes_set = story.get('passes', False)

            # Calculate criteria score
            criteria_score, criteria_passed = self._evaluate_criteria(task, workspace)

            # Detect validation gap
            validation_gap = (criteria_score >= 0.80 and not passes_set)

            error = None if not validation_gap else "Validation gap detected"

            # Cleanup
            subprocess.run(["rm", "-rf", str(workspace)], check=False)

            return ValidationGapResult(
                task_id=task['id'],
                run_number=run_number,
                mode=self.mode,
                criteria_score=criteria_score,
                criteria_passed=criteria_passed,
                passes_field_set=passes_set,
                validation_gap=validation_gap,
                duration_seconds=duration,
                timestamp=datetime.now().isoformat(),
                error_message=error
            )

        except subprocess.TimeoutExpired:
            return ValidationGapResult(
                task_id=task['id'],
                run_number=run_number,
                mode=self.mode,
                criteria_score=0.0,
                criteria_passed={},
                passes_field_set=False,
                validation_gap=False,
                duration_seconds=time.time() - start_time,
                timestamp=datetime.now().isoformat(),
                error_message="Timeout (300s)"
            )

        except Exception as e:
            return ValidationGapResult(
                task_id=task['id'],
                run_number=run_number,
                mode=self.mode,
                criteria_score=0.0,
                criteria_passed={},
                passes_field_set=False,
                validation_gap=False,
                duration_seconds=time.time() - start_time,
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )

    def _create_prd(self, task: Dict) -> Dict:
        """Create PRD data structure from VGAP test case"""
        return {
            "project": f"vgap-test-{task['id']}",
            "branchName": f"test/{task['id']}",
            "description": task['description'],
            "userStories": [
                {
                    "id": "US-001",
                    "title": task['name'],
                    "description": task['description'],
                    "acceptanceCriteria": [
                        ac['description'] for ac in task['acceptance_criteria']
                    ],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                }
            ]
        }

    def _evaluate_criteria(self, task: Dict, workspace: Path) -> Tuple[float, Dict[str, bool]]:
        """
        Evaluate acceptance criteria and calculate weighted score.

        Returns:
            (criteria_score, criteria_passed_dict)
        """
        criteria_passed = {}
        total_score = 0.0

        for ac in task['acceptance_criteria']:
            ac_id = ac['id']
            weight = ac.get('weight', 1.0 / len(task['acceptance_criteria']))

            # Execute validation script
            try:
                script = ac.get('validation_script', '')
                if not script:
                    continue

                result = subprocess.run(
                    script,
                    shell=True,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                passed = (result.returncode == 0)
                criteria_passed[ac_id] = passed

                if passed:
                    total_score += weight

            except Exception:
                criteria_passed[ac_id] = False

        return total_score, criteria_passed

    def _print_result(self, result: ValidationGapResult):
        """Print single test result"""
        if result.validation_gap:
            status = "⚠️  VALIDATION GAP"
        elif result.passes_field_set:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"

        print(f"{status} | Score: {result.criteria_score:.2f} | "
              f"Passes: {result.passes_field_set} | "
              f"{result.duration_seconds:.1f}s")

        if result.error_message:
            print(f"    Error: {result.error_message}")

    def _save_result(self, result: ValidationGapResult):
        """Save individual result to JSON"""
        output_file = RESULTS_DIR / f"{result.task_id}_{self.mode}_run{result.run_number}.json"
        with open(output_file, 'w') as f:
            json.dump(asdict(result), f, indent=2)

    def _generate_report(self):
        """Generate comprehensive test report"""
        print(f"\n{'='*70}")
        print(f"VALIDATION GAP TEST RESULTS - Mode: {self.mode.upper()}")
        print(f"{'='*70}\n")

        # Calculate metrics
        total_runs = len(self.results)
        validation_gaps = sum(1 for r in self.results if r.validation_gap)
        passes_set_count = sum(1 for r in self.results if r.passes_field_set)
        high_score_count = sum(1 for r in self.results if r.criteria_score >= 0.80)

        validation_gap_rate = validation_gaps / total_runs if total_runs > 0 else 0
        success_rate = passes_set_count / total_runs if total_runs > 0 else 0

        print(f"Total runs: {total_runs}")
        print(f"High scores (≥0.80): {high_score_count} ({high_score_count/total_runs*100:.1f}%)")
        print(f"passes:true set: {passes_set_count} ({success_rate*100:.1f}%)")
        print(f"Validation gaps: {validation_gaps} ({validation_gap_rate*100:.1f}%)")
        print()

        # Per-task breakdown
        print("Per-Task Results:")
        print("-" * 70)

        by_task = {}
        for result in self.results:
            if result.task_id not in by_task:
                by_task[result.task_id] = []
            by_task[result.task_id].append(result)

        for task_id, results in sorted(by_task.items()):
            gaps = sum(1 for r in results if r.validation_gap)
            avg_score = sum(r.criteria_score for r in results) / len(results)
            passes_count = sum(1 for r in results if r.passes_field_set)

            print(f"{task_id}: {passes_count}/{len(results)} passed | "
                  f"Avg score: {avg_score:.2f} | "
                  f"Gaps: {gaps}")

        # Save summary report
        report_file = RESULTS_DIR / f"summary_{self.mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report = {
            "mode": self.mode,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_runs": total_runs,
                "high_score_count": high_score_count,
                "passes_set_count": passes_set_count,
                "validation_gaps": validation_gaps,
                "validation_gap_rate": validation_gap_rate,
                "success_rate": success_rate
            },
            "by_task": {
                task_id: {
                    "runs": len(results),
                    "passes_set": sum(1 for r in results if r.passes_field_set),
                    "validation_gaps": sum(1 for r in results if r.validation_gap),
                    "avg_score": sum(r.criteria_score for r in results) / len(results)
                }
                for task_id, results in by_task.items()
            },
            "all_results": [asdict(r) for r in self.results]
        }

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Report saved to: {report_file}")


def compare_results():
    """Compare baseline vs with-fixes results"""
    print(f"\n{'='*70}")
    print("COMPARING BASELINE vs WITH-FIXES")
    print(f"{'='*70}\n")

    # Find latest reports
    baseline_reports = sorted(RESULTS_DIR.glob("summary_baseline_*.json"))
    fixes_reports = sorted(RESULTS_DIR.glob("summary_with_fixes_*.json"))

    if not baseline_reports or not fixes_reports:
        print("ERROR: Need both baseline and with-fixes reports to compare")
        print(f"Found {len(baseline_reports)} baseline reports")
        print(f"Found {len(fixes_reports)} with-fixes reports")
        return

    # Load latest reports
    with open(baseline_reports[-1]) as f:
        baseline = json.load(f)

    with open(fixes_reports[-1]) as f:
        fixes = json.load(f)

    # Compare metrics
    baseline_gap_rate = baseline['summary']['validation_gap_rate']
    fixes_gap_rate = fixes['summary']['validation_gap_rate']
    improvement = baseline_gap_rate - fixes_gap_rate

    baseline_success = baseline['summary']['success_rate']
    fixes_success = fixes['summary']['success_rate']
    success_improvement = fixes_success - baseline_success

    print("Validation Gap Rate:")
    print(f"  Baseline:   {baseline_gap_rate*100:.1f}%")
    print(f"  With fixes: {fixes_gap_rate*100:.1f}%")
    print(f"  Improvement: {improvement*100:.1f}% reduction")
    print()

    print("Success Rate (passes:true set correctly):")
    print(f"  Baseline:   {baseline_success*100:.1f}%")
    print(f"  With fixes: {fixes_success*100:.1f}%")
    print(f"  Improvement: +{success_improvement*100:.1f}%")
    print()

    # Per-task comparison
    print("Per-Task Comparison:")
    print("-" * 70)

    for task_id in baseline['by_task'].keys():
        baseline_task = baseline['by_task'][task_id]
        fixes_task = fixes['by_task'].get(task_id, {})

        baseline_gaps = baseline_task['validation_gaps']
        fixes_gaps = fixes_task.get('validation_gaps', 0)

        print(f"{task_id}: {baseline_gaps} gaps → {fixes_gaps} gaps "
              f"({'✓' if fixes_gaps < baseline_gaps else '=' if fixes_gaps == baseline_gaps else '✗'})")

    # Overall assessment
    print(f"\n{'='*70}")
    print("ASSESSMENT")
    print(f"{'='*70}\n")

    if fixes_gap_rate < baseline_gap_rate * 0.25:
        print("✅ EXCELLENT: Priority 1 fixes reduced validation gaps by >75%")
    elif fixes_gap_rate < baseline_gap_rate * 0.50:
        print("✓ GOOD: Priority 1 fixes reduced validation gaps by >50%")
    elif fixes_gap_rate < baseline_gap_rate:
        print("~ OK: Priority 1 fixes reduced validation gaps but not dramatically")
    else:
        print("✗ NO IMPROVEMENT: Priority 1 fixes did not reduce validation gaps")


def main():
    parser = argparse.ArgumentParser(description="Validation Gap Test Suite")
    parser.add_argument("--baseline", action="store_true",
                       help="Run tests in baseline mode (without Priority 1 fixes)")
    parser.add_argument("--with-fixes", action="store_true",
                       help="Run tests with Priority 1 fixes enabled")
    parser.add_argument("--compare", action="store_true",
                       help="Compare baseline vs with-fixes results")
    parser.add_argument("--runs", type=int, default=3,
                       help="Number of runs per test case (default: 3)")

    args = parser.parse_args()

    if args.compare:
        compare_results()
    elif args.baseline:
        tester = ValidationGapTester(mode="baseline")
        tester.run_tests(runs_per_case=args.runs)
    elif args.with_fixes:
        tester = ValidationGapTester(mode="with_fixes")
        tester.run_tests(runs_per_case=args.runs)
    else:
        # Default: run with fixes
        tester = ValidationGapTester(mode="with_fixes")
        tester.run_tests(runs_per_case=args.runs)


if __name__ == "__main__":
    main()
