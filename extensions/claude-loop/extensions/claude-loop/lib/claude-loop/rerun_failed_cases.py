#!/usr/bin/env python3
"""
Re-run only the 7 failed cases from benchmark v2
With debug logging enabled to capture what's happening
"""

import subprocess
import json
import time
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

CLAUDE_LOOP_SCRIPT = Path("/Users/jialiang.wu/Documents/Projects/claude-loop/claude-loop.sh")
TASKS_DIR = Path("/Users/jialiang.wu/Documents/Projects/benchmark-tasks")
RESULTS_FILE = Path("/Users/jialiang.wu/Documents/Projects/benchmark-results/benchmark_failed_cases_rerun.json")
TIMEOUT_SECONDS = 3600

# The 7 failed cases from v2
FAILED_CASES = [
    ("TASK-003", 4),
    ("TASK-004", 1),
    ("TASK-004", 4),
    ("TASK-005", 5),
    ("TASK-006", 2),
    ("TASK-007", 1),
    ("TASK-010", 2),
]

def load_task(task_id: str) -> Optional[Dict]:
    """Load task from YAML file"""
    task_files = list(TASKS_DIR.glob(f"{task_id}-*.yaml"))
    if not task_files:
        print(f"❌ Task {task_id} not found")
        return None
    
    with open(task_files[0], 'r') as f:
        return yaml.safe_load(f)

def create_prd_data(task: Dict) -> Dict:
    """Convert task YAML to PRD format"""
    return {
        "project": f"benchmark-{task['id']}",
        "branchName": f"benchmark/{task['id']}",
        "description": task['description'],
        "userStories": [{
            "id": "US-001",
            "title": task['name'],
            "description": task['description'],
            "acceptanceCriteria": task['acceptance_criteria'],
            "priority": 1,
            "passes": False
        }]
    }

def check_success(prd_file: Path) -> Tuple[bool, Optional[str], float]:
    """Check if task succeeded"""
    try:
        with open(prd_file, 'r') as f:
            prd = json.load(f)
        
        story = prd['userStories'][0]
        passes = story.get('passes', False)
        avg_score = 0.8 if passes else 0.5
        
        # Lenient validation
        if not passes and avg_score >= 0.80:
            passes = True
        
        if passes:
            return True, None, avg_score
        else:
            return False, "Story did not pass validation", avg_score
    except Exception as e:
        return False, f"Error checking success: {e}", 0.0

def extract_metrics(workspace: Path, preserve: bool = False) -> Tuple[int, float, int]:
    """Extract tokens, cost, and complexity from logs"""
    try:
        logs_dir = workspace / ".claude-loop" / "logs"
        print(f"    [DEBUG] Checking logs dir: {logs_dir}")
        print(f"    [DEBUG] Logs dir exists: {logs_dir.exists()}")
        
        if not logs_dir.exists():
            print(f"    [DEBUG] ❌ Logs dir doesn't exist")
            return 0, 0.0, -1
        
        # List all files
        all_files = list(logs_dir.iterdir())
        print(f"    [DEBUG] Files in logs dir: {len(all_files)}")
        for f in all_files:
            print(f"    [DEBUG]   - {f.name}")
        
        # Read token logs
        token_files = list(logs_dir.glob("tokens_*.json"))
        print(f"    [DEBUG] Token files found: {len(token_files)}")
        
        if not token_files:
            print(f"    [DEBUG] ❌ No token files found")
            if preserve:
                print(f"    [DEBUG] ⚠️  Workspace preserved at: {workspace}")
            return 0, 0.0, -1
        
        latest = sorted(token_files)[-1]
        print(f"    [DEBUG] Reading: {latest}")
        
        with open(latest, 'r') as f:
            data = json.load(f)
            print(f"    [DEBUG] Token file contents: {json.dumps(data, indent=6)}")
            
            tokens = data.get('estimated_tokens', 0)
            complexity = data.get('complexity_level', -1)
            agents_enabled = data.get('agents_enabled', 'unknown')
            experience_enabled = data.get('experience_enabled', 'unknown')
            
            # Calculate cost
            cost = (tokens * 0.6 / 1_000_000 * 3.0) + (tokens * 0.4 / 1_000_000 * 15.0)
            
            print(f"    [DEBUG] ✅ Extracted:")
            print(f"    [DEBUG]   - Tokens: {tokens}")
            print(f"    [DEBUG]   - Complexity: {complexity}")
            print(f"    [DEBUG]   - Agents enabled: {agents_enabled}")
            print(f"    [DEBUG]   - Experience enabled: {experience_enabled}")
            print(f"    [DEBUG]   - Cost: ${cost:.4f}")
            
            return tokens, cost, complexity
    
    except Exception as e:
        print(f"    [DEBUG] ❌ Exception in extract_metrics: {e}")
        import traceback
        traceback.print_exc()
        if preserve:
            print(f"    [DEBUG] ⚠️  Workspace preserved at: {workspace}")
        return 0, 0.0, -1

def run_test_case(task: Dict, run_number: int, preserve: bool = False) -> Dict:
    """Run a single test case"""
    task_id = task['id']
    
    print(f"\n{'='*80}")
    print(f"[{task_id}] Run {run_number} - {task['name']}")
    print(f"Tier: {task['tier']} | Difficulty: {task['difficulty']}/5")
    print(f"{'='*80}")
    
    # Create workspace
    timestamp = int(time.time())
    if preserve:
        workspace = Path(f"/tmp/benchmark_debug_{task_id}_run{run_number}_{timestamp}")
    else:
        workspace = Path(f"/tmp/benchmark_rerun_{task_id}_run{run_number}_{timestamp}")
    
    workspace.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create PRD
        prd_data = create_prd_data(task)
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
        
        # Run claude-loop
        cmd = [
            str(CLAUDE_LOOP_SCRIPT),
            "--prd", "./prd.json",
            "-m", "1",
            "--no-dashboard",
            "--no-progress",
        ]
        
        print(f"Running: {' '.join(cmd)}")
        print(f"Workspace: {workspace}")
        
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
            success, error, avg_score = check_success(workspace_prd)
            
            # Extract metrics WITH DEBUG LOGGING
            tokens, cost, complexity = extract_metrics(workspace, preserve=preserve)
            
            print(f"\nCompleted in {elapsed:.1f}s")
            print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
            print(f"Tokens: {tokens} | Cost: ${cost:.4f} | Complexity: {complexity}")
            
            if preserve:
                print(f"\n⚠️  Workspace preserved for inspection: {workspace}")
            
            return {
                "task_id": task_id,
                "run": run_number,
                "success": success,
                "avg_score": avg_score,
                "tokens": tokens,
                "cost": cost,
                "elapsed_time": elapsed,
                "complexity_level": complexity,
                "error": error,
                "tier": task['tier'],
                "difficulty": task['difficulty'],
                "timestamp": datetime.now().isoformat(),
                "workspace": str(workspace) if preserve else None,
            }
        
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"⏱️  TIMEOUT after {elapsed:.1f}s")
            
            if preserve:
                print(f"⚠️  Workspace preserved for inspection: {workspace}")
            
            return {
                "task_id": task_id,
                "run": run_number,
                "success": False,
                "error": "Timeout exceeded",
                "elapsed_time": elapsed,
                "tier": task['tier'],
                "difficulty": task['difficulty'],
                "timestamp": datetime.now().isoformat(),
                "workspace": str(workspace) if preserve else None,
            }
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        if preserve:
            print(f"⚠️  Workspace preserved for inspection: {workspace}")
        
        return {
            "task_id": task_id,
            "run": run_number,
            "success": False,
            "error": str(e),
            "tier": task['tier'],
            "difficulty": task['difficulty'],
            "timestamp": datetime.now().isoformat(),
            "workspace": str(workspace) if preserve else None,
        }
    
    finally:
        # Cleanup workspace (unless preserving)
        if not preserve:
            subprocess.run(["rm", "-rf", str(workspace)], check=False)

def main():
    print("\n" + "="*80)
    print("TARGETED RE-RUN: 7 Failed Cases from Benchmark v2")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  - Claude-Loop script: {CLAUDE_LOOP_SCRIPT}")
    print(f"  - Fix #3: Complexity filtering (line 3835 corrected)")
    print(f"  - Debug logging: ENABLED")
    print(f"  - Cases to run: {len(FAILED_CASES)}")
    print(f"  - Preserve first workspace: YES (for inspection)")
    print()
    
    start_time = time.time()
    results = []
    
    for idx, (task_id, run_num) in enumerate(FAILED_CASES, 1):
        # Load task
        task = load_task(task_id)
        if not task:
            continue
        
        # Preserve first workspace for inspection
        preserve = (idx == 1)
        
        print(f"\n[{idx}/{len(FAILED_CASES)}] Testing case...")
        result = run_test_case(task, run_num, preserve=preserve)
        results.append(result)
        
        # Save after each test
        output = {
            "summary": {
                "total": len(results),
                "successes": sum(1 for r in results if r['success']),
                "failures": sum(1 for r in results if not r['success']),
                "success_rate": sum(1 for r in results if r['success']) / len(results) if results else 0,
            },
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n[Progress: {len(results)}/{len(FAILED_CASES)}]")
    
    elapsed = time.time() - start_time
    
    # Final summary
    successes = sum(1 for r in results if r['success'])
    tokens_captured = sum(1 for r in results if r.get('tokens', 0) > 0)
    complexities = [r.get('complexity_level', -1) for r in results]
    tokens_list = [r.get('tokens', 0) for r in results]
    
    print("\n" + "="*80)
    print("TARGETED RE-RUN COMPLETE")
    print("="*80)
    print()
    print(f"Results: {successes}/{len(results)} succeeded ({successes/len(results)*100:.1f}%)")
    print(f"Total elapsed time: {elapsed/60:.1f} minutes")
    print()
    print("Metrics Analysis:")
    print(f"  Tokens captured: {tokens_captured}/{len(results)} cases")
    print(f"  Complexity levels: {complexities}")
    print(f"  Token counts: {tokens_list}")
    print()
    
    if tokens_captured >= len(results) * 0.8:
        print("✅ Metrics collection WORKING (≥80% captured)")
    else:
        print(f"⚠️  Metrics collection PARTIAL ({tokens_captured}/{len(results)} captured)")
    
    complexity_detected = sum(1 for c in complexities if c != -1)
    if complexity_detected >= len(results) * 0.8:
        print("✅ Complexity filtering WORKING (≥80% detected)")
    else:
        print(f"⚠️  Complexity filtering PARTIAL ({complexity_detected}/{len(results)} detected)")
    
    print()
    print(f"Results saved to: {RESULTS_FILE}")
    
    # Show preserved workspace
    preserved = [r for r in results if r.get('workspace')]
    if preserved:
        print(f"\nPreserved workspace for inspection:")
        print(f"  {preserved[0]['workspace']}")
        print(f"  Check logs at: {preserved[0]['workspace']}/.claude-loop/logs/")

if __name__ == "__main__":
    main()

