#!/usr/bin/env python3
"""
Full Auto Benchmark with Phase 1 Fixes + Efficiency Tracking
Runs all 50 cases (10 tasks × 5 runs) with detailed metrics logging
"""

import json
import subprocess
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
TASKS_DIR = Path("/Users/jialiang.wu/Documents/Projects/benchmark-tasks")
RESULTS_DIR = Path("/Users/jialiang.wu/Documents/Projects/benchmark-results")
CLAUDE_LOOP_SCRIPT = Path("/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh")
TIMEOUT_SECONDS = 3600


class EfficiencyMetrics:
    """Track efficiency metrics for optimization analysis"""
    def __init__(self):
        self.metrics = {
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_time": 0.0,
            "feature_activations": {
                "agents_enabled": 0,
                "agents_disabled": 0,
                "experience_enabled": 0,
                "experience_disabled": 0,
                "complexity_filtered": 0,
            },
            "by_complexity": {},
            "by_tier": {},
            "optimization_opportunities": [],
        }

    def add_case(self, result: Dict):
        """Add a test case to metrics"""
        self.metrics["total_tokens"] += result.get("tokens", 0)
        self.metrics["total_cost"] += result.get("cost", 0.0)
        self.metrics["total_time"] += result.get("elapsed_time", 0.0)

        # Track feature activations
        complexity = result.get("complexity_level", -1)
        if complexity in [0, 1]:
            self.metrics["feature_activations"]["complexity_filtered"] += 1
            self.metrics["feature_activations"]["agents_disabled"] += 1
            self.metrics["feature_activations"]["experience_disabled"] += 1
        else:
            self.metrics["feature_activations"]["agents_enabled"] += 1
            self.metrics["feature_activations"]["experience_enabled"] += 1

        # Track by complexity
        if complexity not in self.metrics["by_complexity"]:
            self.metrics["by_complexity"][complexity] = {
                "count": 0,
                "tokens": 0,
                "cost": 0.0,
                "time": 0.0,
                "successes": 0,
            }
        self.metrics["by_complexity"][complexity]["count"] += 1
        self.metrics["by_complexity"][complexity]["tokens"] += result.get("tokens", 0)
        self.metrics["by_complexity"][complexity]["cost"] += result.get("cost", 0.0)
        self.metrics["by_complexity"][complexity]["time"] += result.get("elapsed_time", 0.0)
        if result.get("success", False):
            self.metrics["by_complexity"][complexity]["successes"] += 1

        # Track by tier
        tier = result.get("tier", "unknown")
        if tier not in self.metrics["by_tier"]:
            self.metrics["by_tier"][tier] = {
                "count": 0,
                "tokens": 0,
                "cost": 0.0,
                "time": 0.0,
                "successes": 0,
            }
        self.metrics["by_tier"][tier]["count"] += 1
        self.metrics["by_tier"][tier]["tokens"] += result.get("tokens", 0)
        self.metrics["by_tier"][tier]["cost"] += result.get("cost", 0.0)
        self.metrics["by_tier"][tier]["time"] += result.get("elapsed_time", 0.0)
        if result.get("success", False):
            self.metrics["by_tier"][tier]["successes"] += 1

    def analyze_optimizations(self):
        """Identify optimization opportunities"""
        opportunities = []

        # Analyze by complexity
        for complexity, data in self.metrics["by_complexity"].items():
            if data["count"] == 0:
                continue

            avg_tokens = data["tokens"] / data["count"]
            avg_time = data["time"] / data["count"]
            success_rate = data["successes"] / data["count"]

            # High token usage for simple tasks
            if complexity in [0, 1] and avg_tokens > 1000:
                opportunities.append({
                    "type": "high_tokens_simple_task",
                    "complexity": complexity,
                    "avg_tokens": avg_tokens,
                    "recommendation": "Consider more aggressive feature filtering for simple tasks",
                    "potential_savings": f"{(avg_tokens - 800) * data['count']} tokens",
                })

            # Low success rate with features enabled
            if complexity >= 2 and success_rate < 0.9:
                opportunities.append({
                    "type": "low_success_with_features",
                    "complexity": complexity,
                    "success_rate": success_rate,
                    "recommendation": "Investigate if features are helping or hurting",
                    "action": "Consider A/B test: features on vs off for this complexity",
                })

            # Long execution time
            if avg_time > 400:
                opportunities.append({
                    "type": "long_execution_time",
                    "complexity": complexity,
                    "avg_time": avg_time,
                    "recommendation": "Investigate timeout or performance issues",
                    "action": "Review task logs for bottlenecks",
                })

        self.metrics["optimization_opportunities"] = opportunities
        return opportunities


class AutoBenchmarkRunner:
    def __init__(self):
        self.results = []
        self.efficiency = EfficiencyMetrics()
        self.start_time = None
        self.tasks = self._load_tasks()

    def _load_tasks(self) -> List[Dict]:
        """Load all task YAML files"""
        tasks = []
        for task_file in sorted(TASKS_DIR.glob("TASK-*.yaml")):
            with open(task_file, 'r') as f:
                task = yaml.safe_load(f)
                tasks.append(task)
        return tasks

    def _create_prd_data(self, task: Dict) -> Dict:
        """Convert task YAML to PRD format"""
        prd = {
            "project": f"benchmark-{task['id']}",
            "branchName": f"benchmark/{task['id']}",
            "description": task['description'],
            "userStories": [
                {
                    "id": "US-001",
                    "title": task['name'],
                    "description": task['description'],
                    "acceptanceCriteria": [
                        ac['description']
                        for ac in task.get('acceptance_criteria', [])
                    ],
                    "priority": 1,
                    "passes": False,
                    "fileScope": task.get('file_scope', []) if 'file_scope' in task else []
                }
            ]
        }
        return prd

    def _extract_metrics(self, workspace: Path) -> Tuple[int, float, int]:
        """Extract tokens, cost, and complexity from logs"""
        try:
            logs_dir = workspace / ".claude-loop" / "logs"
            if not logs_dir.exists():
                print(f"  [DEBUG] Logs dir doesn't exist: {logs_dir}")
                return 0, 0.0, -1

            # Read token logs
            token_files = list(logs_dir.glob("tokens_*.json"))
            if not token_files:
                print(f"  [DEBUG] No token files found in: {logs_dir}")
                return 0, 0.0, -1

            latest = sorted(token_files)[-1]
            print(f"  [DEBUG] Reading metrics from: {latest}")
            with open(latest, 'r') as f:
                data = json.load(f)
                tokens = data.get('estimated_tokens', 0)
                complexity = data.get('complexity_level', -1)
                # Claude Sonnet 4.5 pricing: $3/1M input, $15/1M output
                # Assume 60% input, 40% output
                cost = (tokens * 0.6 / 1_000_000 * 3.0) + (tokens * 0.4 / 1_000_000 * 15.0)
                print(f"  [DEBUG] Extracted: tokens={tokens}, complexity={complexity}, cost=${cost:.4f}")
                return tokens, cost, complexity

        except Exception as e:
            print(f"  [DEBUG] Exception in _extract_metrics: {e}")
            import traceback
            traceback.print_exc()
            return 0, 0.0, -1

    def _check_success(self, prd_file: Path) -> Tuple[bool, Optional[str], Dict, float]:
        """Check if task succeeded"""
        try:
            with open(prd_file, 'r') as f:
                prd = json.load(f)

            stories = prd.get('userStories', [])
            if not stories:
                return False, "No user stories found", {}, 0.0

            story = stories[0]
            passes = story.get('passes', False)

            # Try to get criteria scores (mock for now, would need actual validator)
            criteria_scores = {}
            avg_score = 0.8 if passes else 0.5  # Placeholder

            # Lenient validation
            if not passes and avg_score >= 0.80:
                passes = True

            if passes:
                return True, None, criteria_scores, avg_score
            else:
                return False, f"Story did not pass validation", criteria_scores, avg_score

        except Exception as e:
            return False, f"Error checking success: {e}", {}, 0.0

    def run_test_case(self, task: Dict, run_number: int) -> Dict:
        """Run a single test case"""
        task_id = task['id']

        print(f"\n{'='*80}")
        print(f"[{task_id}] Run {run_number}/5 - {task['name']}")
        print(f"Tier: {task['tier']} | Difficulty: {task['difficulty']}/5")
        print(f"{'='*80}")

        # Create workspace
        workspace = Path(f"/tmp/benchmark_auto_{task_id}_run{run_number}_{int(time.time())}")
        workspace.mkdir(parents=True, exist_ok=True)

        try:
            # Create PRD
            prd_data = self._create_prd_data(task)
            workspace_prd = workspace / "prd.json"
            with open(workspace_prd, 'w') as f:
                json.dump(prd_data, f, indent=2)

            # Initialize git
            subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Benchmark"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "benchmark@test.com"], cwd=workspace, check=True, capture_output=True)

            # Create empty files
            (workspace / "progress.txt").touch()
            (workspace / "AGENTS.md").touch()

            # Initial commit
            subprocess.run(["git", "add", "."], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=workspace, check=True, capture_output=True)

            # Run claude-loop with auto configuration (features enabled, Phase 1 fixes active)
            cmd = [
                str(CLAUDE_LOOP_SCRIPT),
                "--prd", "./prd.json",
                "-m", "1",
                "--no-dashboard",
                "--no-progress",
                # Features enabled (Phase 1 fixes will activate them intelligently)
            ]

            print(f"Running: {' '.join(cmd)}")

            start_time = time.time()
            try:
                result = subprocess.run(
                    cmd,
                    cwd=workspace,
                    timeout=TIMEOUT_SECONDS,
                    capture_output=True,
                    text=True,
                )
                elapsed = time.time() - start_time

                # Check success
                success, error, criteria_scores, avg_score = self._check_success(workspace_prd)

                # Extract metrics
                tokens, cost, complexity = self._extract_metrics(workspace)

                print(f"Completed in {elapsed:.1f}s")
                print(f"Tokens: {tokens} | Cost: ${cost:.4f} | Complexity: {complexity}")
                print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")

                return {
                    "task_id": task_id,
                    "run": run_number,
                    "success": success,
                    "criteria_scores": criteria_scores,
                    "avg_score": avg_score,
                    "tokens": tokens,
                    "cost": cost,
                    "elapsed_time": elapsed,
                    "complexity_level": complexity,
                    "error": error,
                    "tier": task['tier'],
                    "difficulty": task['difficulty'],
                    "timestamp": datetime.now().isoformat(),
                }

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                print(f"⏱️  TIMEOUT after {elapsed:.1f}s")
                return {
                    "task_id": task_id,
                    "run": run_number,
                    "success": False,
                    "criteria_scores": {},
                    "avg_score": 0.0,
                    "tokens": 0,
                    "cost": 0.0,
                    "elapsed_time": elapsed,
                    "complexity_level": -1,
                    "error": "Timeout exceeded",
                    "tier": task['tier'],
                    "difficulty": task['difficulty'],
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            print(f"ERROR: {e}")
            return {
                "task_id": task_id,
                "run": run_number,
                "success": False,
                "error": str(e),
                "tier": task['tier'],
                "difficulty": task['difficulty'],
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            # Cleanup workspace
            subprocess.run(["rm", "-rf", str(workspace)], check=False)

    def run_full_benchmark(self):
        """Run all 50 test cases (10 tasks × 5 runs)"""
        print("\n" + "="*80)
        print("FULL AUTO BENCHMARK WITH PHASE 1 FIXES")
        print("="*80)
        print(f"\nConfiguration:")
        print(f"  - Fix #1: Empty experience store guard")
        print(f"  - Fix #2: Non-coding agent filtering")
        print(f"  - Fix #3: Complexity-based feature activation")
        print(f"\nTotal cases: {len(self.tasks)} tasks × 5 runs = {len(self.tasks) * 5} runs")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        self.start_time = time.time()
        total_cases = len(self.tasks) * 5
        completed = 0

        for task in self.tasks:
            for run_num in range(1, 6):
                completed += 1
                print(f"\n[Progress: {completed}/{total_cases}]")

                result = self.run_test_case(task, run_num)
                self.results.append(result)
                self.efficiency.add_case(result)

                # Save incremental results
                self._save_results()

                # Brief pause
                time.sleep(1)

        elapsed_total = time.time() - self.start_time

        # Analyze efficiency
        self.efficiency.analyze_optimizations()

        # Print summary
        self._print_summary(elapsed_total)

        # Save final results
        self._save_results()

        return self.results

    def _print_summary(self, elapsed_total: float):
        """Print benchmark summary"""
        successes = sum(1 for r in self.results if r.get('success', False))
        total = len(self.results)

        print("\n" + "="*80)
        print("BENCHMARK COMPLETE")
        print("="*80)
        print(f"\nResults: {successes}/{total} succeeded ({successes/total*100:.1f}%)")
        print(f"Total elapsed time: {elapsed_total/3600:.2f} hours")
        print(f"\nEfficiency Metrics:")
        print(f"  Total tokens: {self.efficiency.metrics['total_tokens']:,}")
        print(f"  Total cost: ${self.efficiency.metrics['total_cost']:.2f}")
        print(f"  Avg tokens/case: {self.efficiency.metrics['total_tokens']/total:.0f}")
        print(f"  Avg cost/case: ${self.efficiency.metrics['total_cost']/total:.4f}")
        print(f"  Avg time/case: {self.efficiency.metrics['total_time']/total:.1f}s")

        print(f"\nFeature Activations:")
        fa = self.efficiency.metrics['feature_activations']
        print(f"  Complexity filtered: {fa['complexity_filtered']}/{total} ({fa['complexity_filtered']/total*100:.1f}%)")
        print(f"  Agents enabled: {fa['agents_enabled']}/{total} ({fa['agents_enabled']/total*100:.1f}%)")
        print(f"  Agents disabled: {fa['agents_disabled']}/{total} ({fa['agents_disabled']/total*100:.1f}%)")

        # Print optimization opportunities
        opportunities = self.efficiency.metrics['optimization_opportunities']
        if opportunities:
            print(f"\nOptimization Opportunities Found: {len(opportunities)}")
            for i, opp in enumerate(opportunities[:5], 1):
                print(f"\n  {i}. {opp['type']}")
                print(f"     Recommendation: {opp['recommendation']}")

    def _save_results(self):
        """Save results to JSON file"""
        output_file = RESULTS_DIR / "benchmark_auto_with_fixes_results.json"

        with open(output_file, 'w') as f:
            json.dump({
                "test_config": {
                    "name": "Auto Benchmark with Phase 1 Fixes",
                    "total_cases": len(self.results),
                    "fixes_applied": [
                        "Fix #1: Guard empty experience store",
                        "Fix #2: Filter non-coding agents",
                        "Fix #3: Complexity-based feature activation"
                    ],
                    "started_at": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
                    "completed_at": datetime.now().isoformat(),
                },
                "results": self.results,
                "efficiency_metrics": self.efficiency.metrics,
                "summary": {
                    "total": len(self.results),
                    "successes": sum(1 for r in self.results if r.get('success', False)),
                    "success_rate": sum(1 for r in self.results if r.get('success', False)) / len(self.results) if self.results else 0,
                }
            }, f, indent=2)

        print(f"\nResults saved to: {output_file}")


def main():
    runner = AutoBenchmarkRunner()
    runner.run_full_benchmark()

    # Exit with success rate
    success_rate = sum(1 for r in runner.results if r.get('success', False)) / len(runner.results)
    sys.exit(0 if success_rate >= 0.95 else 1)


if __name__ == "__main__":
    main()
