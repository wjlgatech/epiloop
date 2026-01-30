#!/usr/bin/env python3
"""
Flask web dashboard for claude-loop monitoring.

This dashboard provides a web interface to view run history, metrics, and analytics
for claude-loop executions. It reads from the .claude-loop/runs/ directory structure.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from flask import Flask, render_template, jsonify, abort, request

app = Flask(__name__)


def _load_json_file(file_path: Path) -> dict[str, Any] | None:
    """
    Load a JSON file, handling malformed JSON with leading decimals.

    The monitoring module may output values like .034170 instead of 0.034170.
    This function fixes that before parsing.

    Returns:
        Parsed JSON dict or None if file doesn't exist or can't be parsed.
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path) as f:
            content = f.read()

        # Try standard JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fix leading decimals: .123 -> 0.123
            # Match decimal numbers that start with a period (not preceded by digit or other period)
            fixed_content = re.sub(r'(?<![0-9.])\.(\d+)', r'0.\1', content)
            return json.loads(fixed_content)
    except (json.JSONDecodeError, IOError):
        return None

# Default port for the dashboard
DEFAULT_PORT = 3000

# Path to the claude-loop runs directory (relative to project root)
RUNS_DIR = Path(__file__).parent.parent / ".claude-loop" / "runs"

# Path to improvements directory
IMPROVEMENTS_DIR = Path(__file__).parent.parent / ".claude-loop" / "improvements"

# Path to capability gaps registry
CAPABILITY_GAPS_FILE = Path(__file__).parent.parent / ".claude-loop" / "capability_gaps.json"

# Path to execution log for pattern analysis
EXECUTION_LOG_FILE = Path(__file__).parent.parent / ".claude-loop" / "execution_log.jsonl"

# Path to improvement history
IMPROVEMENT_HISTORY_FILE = Path(__file__).parent.parent / ".claude-loop" / "improvement_history.jsonl"

# Path to capability inventory
CAPABILITY_INVENTORY_FILE = Path(__file__).parent.parent / ".claude-loop" / "capability_inventory.json"


def get_all_runs() -> list[dict[str, Any]]:
    """
    Read all run summaries from the .claude-loop/runs/ directory.

    Returns:
        List of run summary dictionaries, sorted by timestamp (newest first).
        Each dictionary is normalized to have consistent fields:
        - run_id: Directory name (timestamp)
        - project: Project name (from prd.json or "Unknown")
        - stories_completed: Number of completed stories
        - stories_total: Total number of stories
        - total_iterations: Total iterations run
        - total_cost: Total cost in USD
        - total_duration_ms: Total wall duration in milliseconds
        - status: Run status (complete, error, in_progress)
        - has_report: Whether HTML report exists
    """
    runs = []

    if not RUNS_DIR.exists():
        return runs

    for run_dir in RUNS_DIR.iterdir():
        if not run_dir.is_dir():
            continue

        summary_file = run_dir / "summary.json"
        metrics_file = run_dir / "metrics.json"

        run_data: dict[str, Any] = {
            "run_id": run_dir.name,
            "project": "Unknown",
            "stories_completed": 0,
            "stories_total": 0,
            "total_iterations": 0,
            "total_cost": 0.0,
            "total_duration_ms": 0,
            "status": "unknown",
            "has_report": (run_dir / "report.html").exists(),
            "iterations": [],
        }

        # Try to load project name from prd.json in project root
        run_data["project"] = _get_project_name()

        # Try to load summary first, fall back to metrics
        summary = _load_json_file(summary_file)
        if summary:
            # Normalize summary.json fields to expected format
            if "stories" in summary:
                run_data["stories_completed"] = summary["stories"].get("completed", 0)
                run_data["stories_total"] = summary["stories"].get("total", 0)
                run_data["total_iterations"] = summary["stories"].get("total", 0)
            if "cost" in summary:
                run_data["total_cost"] = summary["cost"].get("total_usd", 0.0)
            if "duration" in summary:
                run_data["total_duration_ms"] = summary["duration"].get("wall_ms", 0)
            run_data["status"] = summary.get("status", "unknown")
            # Keep original data for reference
            run_data["_summary"] = summary

        # Load metrics for iteration details
        metrics = _load_json_file(metrics_file)
        if metrics:
            run_data["iterations"] = metrics.get("iterations", [])
            # If summary wasn't available, use metrics for totals
            if summary is None:
                totals = metrics.get("totals", {})
                run_data["total_iterations"] = totals.get("iterations", 0)
                run_data["total_cost"] = totals.get("cost_usd", 0.0)
                run_data["total_duration_ms"] = totals.get("wall_duration_ms", 0)
                # Estimate stories from iterations
                iterations = metrics.get("iterations", [])
                completed = sum(1 for i in iterations if i.get("status") in ["complete", "completed"])
                run_data["stories_completed"] = completed
                run_data["stories_total"] = len(iterations)
            # Keep original data for reference
            run_data["_metrics"] = metrics

        # Skip runs with no data
        if run_data["total_iterations"] == 0 and not run_data["iterations"]:
            continue

        runs.append(run_data)

    # Sort by run_id (timestamp) descending
    runs.sort(key=lambda x: x.get("run_id", ""), reverse=True)

    return runs


def get_run_details(run_id: str) -> dict[str, Any] | None:
    """
    Get detailed information for a specific run.

    Args:
        run_id: The run directory name (timestamp).

    Returns:
        Dictionary with run details or None if not found.
        Includes normalized summary fields, metrics, agent cost breakdown,
        and lessons learned from progress.txt.
    """
    run_dir = RUNS_DIR / run_id

    if not run_dir.exists() or not run_dir.is_dir():
        return None

    details: dict[str, Any] = {
        "run_id": run_id,
        "summary": None,
        "metrics": None,
        "improvements": None,
        "has_report": (run_dir / "report.html").exists(),
        "agent_costs": [],  # Cost breakdown by agent
        "lessons_learned": [],  # Extracted from progress.txt
    }

    # Load summary
    summary_file = run_dir / "summary.json"
    summary = _load_json_file(summary_file)
    if summary:
        # Normalize summary fields for template
        normalized = {
            "project": summary.get("project", "Unknown"),
            "branch": summary.get("branch", ""),
            "status": summary.get("status", "unknown"),
        }
        # Extract from nested structure
        if "stories" in summary:
            normalized["stories_completed"] = summary["stories"].get("completed", 0)
            normalized["stories_total"] = summary["stories"].get("total", 0)
        if "cost" in summary:
            normalized["total_cost"] = summary["cost"].get("total_usd", 0.0)
        if "duration" in summary:
            normalized["total_duration_ms"] = summary["duration"].get("wall_ms", 0)
        # Keep original data and add normalized fields
        details["summary"] = {**summary, **normalized}

    # Load metrics
    metrics_file = run_dir / "metrics.json"
    metrics = _load_json_file(metrics_file)
    if metrics:
        details["metrics"] = metrics

        # Build normalized summary from metrics if no summary file
        if details["summary"] is None:
            totals = metrics.get("totals", {})
            iterations = metrics.get("iterations", [])
            completed = sum(1 for i in iterations if i.get("status") in ["complete", "completed"])
            details["summary"] = {
                "project": _get_project_name(),
                "branch": "",
                "status": "unknown",
                "stories_completed": completed,
                "stories_total": len(iterations),
                "total_cost": totals.get("cost_usd", 0.0),
                "total_duration_ms": totals.get("wall_duration_ms", 0),
            }
        else:
            # Ensure we have cost and duration from metrics if not in summary
            totals = metrics.get("totals", {})
            if not details["summary"].get("total_cost"):
                details["summary"]["total_cost"] = totals.get("cost_usd", 0.0)
            if not details["summary"].get("total_duration_ms"):
                details["summary"]["total_duration_ms"] = totals.get("wall_duration_ms", 0)

        # Calculate cost breakdown by agent
        details["agent_costs"] = _calculate_agent_costs(metrics.get("iterations", []))

    # Load improvements
    improvements_file = run_dir / "improvements.json"
    improvements = _load_json_file(improvements_file)
    if improvements:
        details["improvements"] = improvements

    # Load lessons learned from progress.txt
    progress_file = Path(__file__).parent.parent / "progress.txt"
    if progress_file.exists():
        details["lessons_learned"] = _extract_lessons_learned(progress_file)

    return details


def _get_project_name() -> str:
    """Get project name from prd.json."""
    prd_file = Path(__file__).parent.parent / "prd.json"
    if prd_file.exists():
        try:
            with open(prd_file) as f:
                prd = json.load(f)
                return prd.get("project", "Unknown")
        except (json.JSONDecodeError, IOError):
            pass
    return "Unknown"


def _calculate_agent_costs(iterations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Calculate cost breakdown by agent from iteration data.

    Returns:
        List of dicts with agent name, usage count, and total cost.
    """
    agent_stats: dict[str, dict[str, Any]] = {}

    for iteration in iterations:
        agents_used = iteration.get("agents_used", [])
        cost = iteration.get("cost_usd", 0.0)

        # Handle both string and list formats
        if isinstance(agents_used, str):
            agents_used = [a.strip() for a in agents_used.split(",") if a.strip()]

        if not agents_used:
            agents_used = ["(no agent)"]

        # Distribute cost evenly among agents used in this iteration
        cost_per_agent = cost / len(agents_used) if agents_used else cost

        for agent in agents_used:
            if agent not in agent_stats:
                agent_stats[agent] = {"agent": agent, "count": 0, "total_cost": 0.0}
            agent_stats[agent]["count"] += 1
            agent_stats[agent]["total_cost"] += cost_per_agent

    # Sort by total cost descending
    return sorted(agent_stats.values(), key=lambda x: x["total_cost"], reverse=True)


def _extract_lessons_learned(progress_file: Path) -> list[dict[str, Any]]:
    """
    Extract lessons learned from progress.txt.

    Returns:
        List of dicts with story, status, and learnings.
    """
    import re

    lessons = []

    try:
        content = progress_file.read_text()

        # Pattern to match iteration entries
        iteration_pattern = r"### Iteration:.*?\n\*\*Story\*\*:\s*(.+?)\n\*\*Status\*\*:\s*(.+?)\n.*?(?:\*\*Learnings for future iterations\*\*:\n(.*?)(?=\n---|$))"

        for match in re.finditer(iteration_pattern, content, re.DOTALL):
            story = match.group(1).strip()
            status = match.group(2).strip()
            learnings_text = match.group(3).strip() if match.group(3) else ""

            # Parse bullet points
            learnings_list = []
            for line in learnings_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    learnings_list.append(line[2:].strip())

            if learnings_list:
                lessons.append({
                    "story": story,
                    "status": status,
                    "learnings": learnings_list
                })
    except IOError:
        pass

    return lessons


def get_agent_analytics() -> dict[str, Any]:
    """
    Aggregate agent usage statistics across all runs.

    Returns:
        Dictionary containing:
        - agents: List of agent stats (name, times used, total cost, success rate, avg cost)
        - most_expensive_agent: Agent with highest total cost
        - most_effective_agent: Agent with highest success rate (min 2 uses)
        - most_used_agent: Agent used most frequently
        - improvements: Aggregated improvement suggestions from runs
        - totals: Overall totals across all agents
    """
    runs = get_all_runs()
    agent_stats: dict[str, dict[str, Any]] = {}

    # Collect all improvements from runs
    all_improvements: list[dict[str, Any]] = []

    for run in runs:
        # Process iterations for agent usage
        iterations = run.get("iterations", [])
        for iteration in iterations:
            agents_used = iteration.get("agents_used", [])
            cost = iteration.get("cost_usd", 0.0)
            status = iteration.get("status", "unknown")

            # Determine if iteration was successful
            is_success = status.lower() in ["complete", "completed", "success"]

            # Handle both string and list formats
            if isinstance(agents_used, str):
                agents_used = [a.strip() for a in agents_used.split(",") if a.strip()]

            if not agents_used:
                agents_used = ["(no agent)"]

            # Distribute cost evenly among agents
            cost_per_agent = cost / len(agents_used) if agents_used else cost

            for agent in agents_used:
                if agent not in agent_stats:
                    agent_stats[agent] = {
                        "agent": agent,
                        "times_used": 0,
                        "total_cost": 0.0,
                        "successful": 0,
                        "failed": 0,
                        "runs": set(),  # Track unique runs this agent was used in
                    }
                agent_stats[agent]["times_used"] += 1
                agent_stats[agent]["total_cost"] += cost_per_agent
                if is_success:
                    agent_stats[agent]["successful"] += 1
                else:
                    agent_stats[agent]["failed"] += 1
                agent_stats[agent]["runs"].add(run.get("run_id", ""))

        # Load improvements from run directory
        run_id = run.get("run_id", "")
        if run_id:
            improvements_file = RUNS_DIR / run_id / "improvements.json"
            improvements = _load_json_file(improvements_file)
            if improvements and "suggestions" in improvements:
                for suggestion in improvements["suggestions"]:
                    suggestion["run_id"] = run_id
                    all_improvements.append(suggestion)

    # Calculate success rate and average cost for each agent
    agents_list = []
    for agent, stats in agent_stats.items():
        total_uses = stats["times_used"]
        success_rate = (stats["successful"] / total_uses * 100) if total_uses > 0 else 0
        avg_cost = stats["total_cost"] / total_uses if total_uses > 0 else 0

        agents_list.append({
            "agent": agent,
            "times_used": total_uses,
            "total_cost": stats["total_cost"],
            "successful": stats["successful"],
            "failed": stats["failed"],
            "success_rate": success_rate,
            "avg_cost": avg_cost,
            "runs_count": len(stats["runs"]),
        })

    # Sort by total cost descending
    agents_list.sort(key=lambda x: x["total_cost"], reverse=True)

    # Identify key agents
    most_expensive = agents_list[0] if agents_list else None

    # Most effective: highest success rate with minimum 2 uses
    effective_candidates = [a for a in agents_list if a["times_used"] >= 2]
    most_effective = max(effective_candidates, key=lambda x: x["success_rate"]) if effective_candidates else None

    # Most used: highest times_used
    most_used = max(agents_list, key=lambda x: x["times_used"]) if agents_list else None

    # Aggregate improvements by priority
    improvements_by_priority: dict[str, list[dict[str, Any]]] = {
        "high": [],
        "medium": [],
        "low": [],
    }
    for imp in all_improvements:
        priority = imp.get("priority", "medium").lower()
        if priority in improvements_by_priority:
            improvements_by_priority[priority].append(imp)

    # Calculate totals
    total_uses = sum(a["times_used"] for a in agents_list)
    total_successful = sum(a["successful"] for a in agents_list)
    totals: dict[str, Any] = {
        "total_agents": len(agents_list),
        "total_uses": total_uses,
        "total_cost": sum(a["total_cost"] for a in agents_list),
        "total_successful": total_successful,
        "total_failed": sum(a["failed"] for a in agents_list),
        "overall_success_rate": (
            total_successful / total_uses * 100
            if total_uses > 0 else 0.0
        ),
    }

    return {
        "agents": agents_list,
        "most_expensive_agent": most_expensive,
        "most_effective_agent": most_effective,
        "most_used_agent": most_used,
        "improvements": improvements_by_priority,
        "totals": totals,
    }


def get_parallel_stats() -> dict[str, Any]:
    """
    Aggregate parallel execution statistics across all runs.

    Returns:
        Dictionary containing:
        - runs_with_parallel: Number of runs that used parallel execution
        - total_runs: Total number of runs
        - aggregate_parallel: Aggregated parallel execution metrics
        - aggregate_cache: Aggregated cache statistics
        - aggregate_model_usage: Aggregated model usage
        - aggregate_cost_savings: Total cost savings
        - per_run_stats: List of per-run parallel stats
    """
    runs = get_all_runs()

    # Initialize aggregates
    total_runs = len(runs)
    runs_with_parallel = 0

    # Parallel execution aggregates
    total_batches = 0
    total_workers = 0
    max_concurrent_seen = 0
    total_parallel_time_ms = 0
    total_sequential_estimate_ms = 0

    # Model usage aggregates
    total_haiku = 0
    total_sonnet = 0
    total_opus = 0

    # Cache aggregates
    total_cache_hits = 0
    total_cache_misses = 0
    total_tokens_saved = 0

    # Cost aggregates
    total_cost = 0.0
    total_opus_baseline = 0.0

    # Per-run stats
    per_run_stats: list[dict[str, Any]] = []

    for run in runs:
        run_id = run.get("run_id", "")
        run_dir = RUNS_DIR / run_id

        # Load summary for this run
        summary_file = run_dir / "summary.json"
        summary = _load_json_file(summary_file)

        if not summary:
            continue

        run_stats: dict[str, Any] = {
            "run_id": run_id,
            "parallel_enabled": False,
        }

        # Extract parallel info
        parallel_info = summary.get("parallel", {})
        if parallel_info.get("enabled", False):
            runs_with_parallel += 1
            run_stats["parallel_enabled"] = True

            batches = parallel_info.get("batches", 0)
            workers = parallel_info.get("workers_used", 0)
            max_concurrent = parallel_info.get("max_concurrent", 0)
            parallel_time = parallel_info.get("parallel_time_ms", 0)
            sequential_time = parallel_info.get("sequential_estimate_ms", 0)
            speedup = parallel_info.get("speedup_factor", 1.0)
            time_saved = parallel_info.get("time_saved_ms", 0)

            total_batches += batches
            total_workers += workers
            if max_concurrent > max_concurrent_seen:
                max_concurrent_seen = max_concurrent
            total_parallel_time_ms += parallel_time
            total_sequential_estimate_ms += sequential_time

            run_stats["parallel"] = {
                "batches": batches,
                "workers": workers,
                "max_concurrent": max_concurrent,
                "speedup": speedup,
                "time_saved_ms": time_saved,
            }

        # Extract model usage
        model_usage = summary.get("model_usage", {})
        haiku = model_usage.get("haiku", 0)
        sonnet = model_usage.get("sonnet", 0)
        opus = model_usage.get("opus", 0)
        total_haiku += haiku
        total_sonnet += sonnet
        total_opus += opus

        run_stats["model_usage"] = {
            "haiku": haiku,
            "sonnet": sonnet,
            "opus": opus,
        }

        # Extract cache stats
        cache_info = summary.get("cache", {})
        hits = cache_info.get("hits", 0)
        misses = cache_info.get("misses", 0)
        tokens_saved = cache_info.get("saved_tokens_estimate", 0)
        total_cache_hits += hits
        total_cache_misses += misses
        total_tokens_saved += tokens_saved

        run_stats["cache"] = {
            "hits": hits,
            "misses": misses,
            "tokens_saved": tokens_saved,
        }

        # Extract cost info
        cost_info = summary.get("cost", {})
        cost = cost_info.get("total_usd", 0)
        opus_baseline = cost_info.get("opus_baseline_usd", 0)
        total_cost += cost
        total_opus_baseline += opus_baseline

        run_stats["cost"] = {
            "actual": cost,
            "opus_baseline": opus_baseline,
            "savings": opus_baseline - cost,
        }

        per_run_stats.append(run_stats)

    # Calculate aggregates
    total_time_saved = total_sequential_estimate_ms - total_parallel_time_ms
    if total_time_saved < 0:
        total_time_saved = 0

    avg_speedup = 1.0
    if total_parallel_time_ms > 0 and total_sequential_estimate_ms > 0:
        avg_speedup = total_sequential_estimate_ms / total_parallel_time_ms

    total_cache_requests = total_cache_hits + total_cache_misses
    cache_hit_rate = 0.0
    if total_cache_requests > 0:
        cache_hit_rate = (total_cache_hits / total_cache_requests) * 100

    total_savings = total_opus_baseline - total_cost
    savings_percent = 0.0
    if total_opus_baseline > 0:
        savings_percent = (total_savings / total_opus_baseline) * 100

    return {
        "runs_with_parallel": runs_with_parallel,
        "total_runs": total_runs,
        "aggregate_parallel": {
            "total_batches": total_batches,
            "total_workers": total_workers,
            "max_concurrent_seen": max_concurrent_seen,
            "total_parallel_time_ms": total_parallel_time_ms,
            "total_sequential_estimate_ms": total_sequential_estimate_ms,
            "total_time_saved_ms": total_time_saved,
            "average_speedup": round(avg_speedup, 2),
            "parallel_time_formatted": format_duration(total_parallel_time_ms),
            "sequential_time_formatted": format_duration(total_sequential_estimate_ms),
            "time_saved_formatted": format_duration(total_time_saved),
        },
        "aggregate_model_usage": {
            "haiku": total_haiku,
            "sonnet": total_sonnet,
            "opus": total_opus,
            "total": total_haiku + total_sonnet + total_opus,
        },
        "aggregate_cache": {
            "total_hits": total_cache_hits,
            "total_misses": total_cache_misses,
            "total_tokens_saved": total_tokens_saved,
            "hit_rate": round(cache_hit_rate, 1),
        },
        "aggregate_cost_savings": {
            "total_actual_cost": round(total_cost, 4),
            "total_opus_baseline": round(total_opus_baseline, 4),
            "total_savings": round(total_savings, 4),
            "savings_percent": round(savings_percent, 1),
        },
        "per_run_stats": per_run_stats,
    }


def get_improvement_prds() -> dict[str, Any]:
    """
    Get all improvement PRDs grouped by status.

    Returns:
        Dictionary with PRDs grouped by status and summary statistics.
    """
    if not IMPROVEMENTS_DIR.exists():
        return {
            "pending_review": [],
            "approved": [],
            "in_progress": [],
            "complete": [],
            "rejected": [],
            "total": 0,
            "by_category": {},
        }

    prds_by_status: dict[str, list[dict[str, Any]]] = {
        "pending_review": [],
        "approved": [],
        "in_progress": [],
        "complete": [],
        "rejected": [],
    }
    by_category: dict[str, int] = {}

    for prd_file in IMPROVEMENTS_DIR.glob("*.json"):
        prd = _load_json_file(prd_file)
        if not prd:
            continue

        status = prd.get("status", "pending_review")
        category = prd.get("gap_category", "UNKNOWN")

        # Count by category
        by_category[category] = by_category.get(category, 0) + 1

        # Add to appropriate status list
        if status in prds_by_status:
            prds_by_status[status].append(prd)
        else:
            prds_by_status["pending_review"].append(prd)

    # Sort each list by priority score
    for status_list in prds_by_status.values():
        status_list.sort(key=lambda p: p.get("priority_score", 0), reverse=True)

    total = sum(len(prds) for prds in prds_by_status.values())

    return {
        **prds_by_status,
        "total": total,
        "by_category": by_category,
    }


def get_capability_gaps() -> dict[str, Any]:
    """
    Get capability gaps from the registry.

    Returns:
        Dictionary with gaps and summary statistics.
    """
    if not CAPABILITY_GAPS_FILE.exists():
        return {
            "gaps": [],
            "total": 0,
            "active": 0,
            "resolved": 0,
            "by_category": {},
            "top_priority": [],
        }

    data = _load_json_file(CAPABILITY_GAPS_FILE)
    if not data:
        return {
            "gaps": [],
            "total": 0,
            "active": 0,
            "resolved": 0,
            "by_category": {},
            "top_priority": [],
        }

    gaps = list(data.get("gaps", {}).values())
    active_gaps = [g for g in gaps if g.get("status") == "active"]
    resolved_gaps = [g for g in gaps if g.get("status") == "resolved"]

    # Count by category
    by_category: dict[str, int] = {}
    for gap in active_gaps:
        category = gap.get("category", "UNKNOWN")
        by_category[category] = by_category.get(category, 0) + 1

    # Get top 5 priority gaps
    sorted_gaps = sorted(active_gaps, key=lambda g: g.get("priority_score", 0), reverse=True)
    top_priority = sorted_gaps[:5]

    return {
        "gaps": gaps,
        "total": len(gaps),
        "active": len(active_gaps),
        "resolved": len(resolved_gaps),
        "by_category": by_category,
        "top_priority": top_priority,
    }


def get_failure_patterns() -> dict[str, Any]:
    """
    Get failure patterns from execution log analysis.

    Returns:
        Dictionary with pattern statistics.
    """
    if not EXECUTION_LOG_FILE.exists():
        return {
            "total_patterns": 0,
            "total_failures": 0,
            "by_error_type": {},
            "recent_failures": [],
        }

    failures = []
    try:
        with open(EXECUTION_LOG_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("status") != "success":
                        failures.append(entry)
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass

    # Count by error type
    by_error_type: dict[str, int] = {}
    for failure in failures:
        error_type = failure.get("error_type", "unknown")
        by_error_type[error_type] = by_error_type.get(error_type, 0) + 1

    # Get recent failures (last 10)
    recent_failures = sorted(
        failures,
        key=lambda f: f.get("timestamp_start", ""),
        reverse=True
    )[:10]

    return {
        "total_patterns": len(by_error_type),
        "total_failures": len(failures),
        "by_error_type": by_error_type,
        "recent_failures": recent_failures,
    }


def get_improvement_history() -> list[dict[str, Any]]:
    """
    Get improvement history from the history log.

    Returns:
        List of improvement history entries.
    """
    if not IMPROVEMENT_HISTORY_FILE.exists():
        return []

    history = []
    try:
        with open(IMPROVEMENT_HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    history.append(entry)
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass

    # Sort by timestamp descending
    history.sort(key=lambda h: h.get("timestamp", ""), reverse=True)
    return history


def get_capability_coverage() -> dict[str, Any]:
    """
    Get capability coverage statistics.

    Returns:
        Dictionary with coverage metrics.
    """
    if not CAPABILITY_INVENTORY_FILE.exists():
        return {
            "total": 0,
            "available": 0,
            "limited": 0,
            "unavailable": 0,
            "coverage_rate": 0.0,
            "by_category": {},
            "trend": [],
        }

    data = _load_json_file(CAPABILITY_INVENTORY_FILE)
    if not data:
        return {
            "total": 0,
            "available": 0,
            "limited": 0,
            "unavailable": 0,
            "coverage_rate": 0.0,
            "by_category": {},
            "trend": [],
        }

    capabilities = list(data.get("capabilities", {}).values())
    total = len(capabilities)
    available = len([c for c in capabilities if c.get("status") == "available"])
    limited = len([c for c in capabilities if c.get("status") == "limited"])
    unavailable = len([c for c in capabilities if c.get("status") == "unavailable"])

    coverage_rate = (available / total * 100) if total > 0 else 0.0

    # Count by category
    by_category: dict[str, dict[str, int]] = {}
    for cap in capabilities:
        category = cap.get("category", "unknown")
        if category not in by_category:
            by_category[category] = {"total": 0, "available": 0}
        by_category[category]["total"] += 1
        if cap.get("status") == "available":
            by_category[category]["available"] += 1

    return {
        "total": total,
        "available": available,
        "limited": limited,
        "unavailable": unavailable,
        "coverage_rate": coverage_rate,
        "by_category": by_category,
        "trend": [],  # Would require historical tracking
    }


def get_improvement_metrics() -> dict[str, Any]:
    """
    Calculate improvement success rate and other metrics over time.

    Returns:
        Dictionary with improvement metrics.
    """
    history = get_improvement_history()

    if not history:
        return {
            "total_improvements": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
            "by_month": [],
            "recent_activity": [],
        }

    # Count outcomes
    successful = 0
    failed = 0
    for entry in history:
        action = entry.get("action", "")
        if action == "complete":
            successful += 1
        elif action in ["reject", "rollback"]:
            failed += 1

    total = successful + failed
    success_rate = (successful / total * 100) if total > 0 else 0.0

    # Group by month for trend
    by_month: dict[str, dict[str, int]] = {}
    for entry in history:
        timestamp = entry.get("timestamp", "")[:7]  # YYYY-MM
        if timestamp:
            if timestamp not in by_month:
                by_month[timestamp] = {"successful": 0, "failed": 0}
            action = entry.get("action", "")
            if action == "complete":
                by_month[timestamp]["successful"] += 1
            elif action in ["reject", "rollback"]:
                by_month[timestamp]["failed"] += 1

    # Convert to sorted list
    monthly_trend = [
        {"month": month, **counts}
        for month, counts in sorted(by_month.items())
    ]

    return {
        "total_improvements": total,
        "successful": successful,
        "failed": failed,
        "success_rate": success_rate,
        "by_month": monthly_trend,
        "recent_activity": history[:10],
    }


def get_self_improvement_data() -> dict[str, Any]:
    """
    Aggregate all self-improvement related data for the dashboard.

    Returns:
        Complete dictionary of improvement metrics and status.
    """
    prds = get_improvement_prds()
    gaps = get_capability_gaps()
    patterns = get_failure_patterns()
    coverage = get_capability_coverage()
    metrics = get_improvement_metrics()

    return {
        "prds": prds,
        "gaps": gaps,
        "patterns": patterns,
        "coverage": coverage,
        "metrics": metrics,
        "summary": {
            "pending_prds": len(prds.get("pending_review", [])),
            "approved_prds": len(prds.get("approved", [])),
            "in_progress_prds": len(prds.get("in_progress", [])),
            "completed_prds": len(prds.get("complete", [])),
            "active_gaps": gaps.get("active", 0),
            "resolved_gaps": gaps.get("resolved", 0),
            "total_patterns": patterns.get("total_patterns", 0),
            "capability_coverage": coverage.get("coverage_rate", 0.0),
            "success_rate": metrics.get("success_rate", 0.0),
        },
    }


def format_duration(ms: int | float) -> str:
    """Format milliseconds as human-readable duration."""
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_cost(cost: float) -> str:
    """Format cost in USD."""
    return f"${cost:.4f}"


def format_timestamp(ts: str | int | float) -> str:
    """Format timestamp for display."""
    if isinstance(ts, str):
        # Try to parse various timestamp formats
        try:
            # Format: 20260110_163000
            if "_" in ts and len(ts) == 15:
                dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        return ts
    # ts is int | float (numeric timestamp)
    # Unix timestamp in milliseconds
    try:
        dt = datetime.fromtimestamp(ts / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return str(ts)


# Register template filters
app.jinja_env.filters["format_duration"] = format_duration
app.jinja_env.filters["format_cost"] = format_cost
app.jinja_env.filters["format_timestamp"] = format_timestamp


@app.route("/")
def index():
    """Dashboard home - show all runs."""
    runs = get_all_runs()
    return render_template("index.html", runs=runs)


@app.route("/run/<run_id>")
def run_detail(run_id: str):
    """Show details for a specific run."""
    details = get_run_details(run_id)
    if details is None:
        abort(404)
    return render_template("run_detail.html", **cast(dict[str, Any], details))


@app.route("/analytics")
def analytics():
    """Show aggregate analytics across all runs."""
    runs = get_all_runs()
    agent_analytics = get_agent_analytics()
    return render_template("analytics.html", runs=runs, agent_analytics=agent_analytics)


@app.route("/api/runs")
def api_runs():
    """API endpoint - get all runs."""
    runs = get_all_runs()
    return jsonify(runs)


@app.route("/api/run/<run_id>")
def api_run_detail(run_id: str):
    """API endpoint - get run details."""
    details = get_run_details(run_id)
    if details is None:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(details)


@app.route("/api/agents")
def api_agent_analytics():
    """API endpoint - get agent analytics."""
    analytics = get_agent_analytics()
    return jsonify(analytics)


@app.route("/api/parallel-stats")
def api_parallel_stats():
    """
    API endpoint - get parallel execution statistics across all runs.

    Returns aggregated parallel execution metrics including:
    - Total batches executed
    - Total workers used
    - Aggregate time saved
    - Average speedup factor
    - Model usage breakdown
    - Cache statistics
    - Cost savings
    """
    stats = get_parallel_stats()
    return jsonify(stats)


@app.route("/improvements")
def improvements():
    """Show self-improvement dashboard."""
    data = get_self_improvement_data()
    return render_template("improvements.html", **data)


@app.route("/api/improvements")
def api_improvements():
    """
    API endpoint - get self-improvement metrics as JSON.

    Supports optional query parameters:
    - section: Filter to specific section (prds, gaps, patterns, coverage, metrics, summary)

    Returns comprehensive self-improvement data for external monitoring.
    """
    data = get_self_improvement_data()

    # Check for section filter
    section = request.args.get("section")
    if section and section in data:
        return jsonify({section: data[section]})

    return jsonify(data)


@app.route("/api/improvements/prds")
def api_improvement_prds():
    """API endpoint - get improvement PRDs grouped by status."""
    return jsonify(get_improvement_prds())


@app.route("/api/improvements/gaps")
def api_capability_gaps():
    """API endpoint - get capability gaps."""
    return jsonify(get_capability_gaps())


@app.route("/api/improvements/patterns")
def api_failure_patterns():
    """API endpoint - get failure patterns."""
    return jsonify(get_failure_patterns())


@app.route("/api/improvements/coverage")
def api_capability_coverage():
    """API endpoint - get capability coverage."""
    return jsonify(get_capability_coverage())


@app.route("/api/improvements/metrics")
def api_improvement_metrics():
    """API endpoint - get improvement success metrics."""
    return jsonify(get_improvement_metrics())


@app.route("/api/health-indicators")
def api_health_indicators():
    """
    API endpoint - get leading indicator health metrics.

    Returns system health status including:
    - proposal_rate_change: Ratio of recent proposals vs baseline
    - cluster_concentration: Fraction of failures in dominant pattern
    - retrieval_miss_rate: Fraction of unhelpful experience retrievals
    - domain_drift: Fraction of work in unknown domains

    Each indicator has:
    - value: Current numeric value
    - status: RAG status (green/amber/red/unknown)
    - trend: Direction (improving/stable/degrading)
    - message: Human-readable description
    """
    try:
        # Import health indicators module
        import importlib.util
        health_module_path = Path(__file__).parent.parent / "lib" / "health-indicators.py"
        spec = importlib.util.spec_from_file_location("health_indicators", health_module_path)
        health_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(health_module)  # type: ignore

        manager = health_module.HealthIndicatorsManager(
            base_dir=Path(__file__).parent.parent
        )
        snapshot = manager.get_health_snapshot()
        return jsonify(snapshot.to_dict())
    except Exception as e:
        return jsonify({
            "error": str(e),
            "overall_status": "unknown",
            "indicators": {},
            "message": "Failed to compute health indicators",
        }), 500


@app.route("/api/health-indicators/alerts")
def api_health_alerts():
    """API endpoint - get active health alerts."""
    try:
        import importlib.util
        health_module_path = Path(__file__).parent.parent / "lib" / "health-indicators.py"
        spec = importlib.util.spec_from_file_location("health_indicators", health_module_path)
        health_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(health_module)  # type: ignore

        manager = health_module.HealthIndicatorsManager(
            base_dir=Path(__file__).parent.parent
        )
        alerts = manager.get_active_alerts()
        return jsonify([a.to_dict() for a in alerts])
    except Exception as e:
        return jsonify({"error": str(e), "alerts": []}), 500


@app.route("/api/health-indicators/history")
def api_health_history():
    """
    API endpoint - get health indicator history.

    Query parameters:
    - days: Number of days to look back (default: 30)
    - indicator: Filter to specific indicator (optional)
    """
    try:
        import importlib.util
        health_module_path = Path(__file__).parent.parent / "lib" / "health-indicators.py"
        spec = importlib.util.spec_from_file_location("health_indicators", health_module_path)
        health_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(health_module)  # type: ignore

        days = request.args.get("days", 30, type=int)
        indicator = request.args.get("indicator")

        manager = health_module.HealthIndicatorsManager(
            base_dir=Path(__file__).parent.parent
        )
        history = manager.get_history(days=days, indicator=indicator)
        return jsonify({"history": history, "days": days, "indicator": indicator})
    except Exception as e:
        return jsonify({"error": str(e), "history": []}), 500


@app.route("/api/calibration")
def api_calibration():
    """
    API endpoint - get calibration tracking metrics.

    Returns system alignment metrics including:
    - agreement_rate: Overall system-human agreement rate
    - false_positive_rate: Rate of system approving what humans rejected
    - false_negative_rate: Rate of system rejecting what humans approved
    - by_source: Metrics broken down by decision source
    - by_domain: Metrics broken down by domain
    - status: Current calibration status
    - autonomous_eligible: Whether autonomous mode is allowed
    - blocking_reasons: Reasons blocking autonomous mode

    Query parameters:
    - days: Only include decisions from last N days (optional)
    """
    try:
        import importlib.util
        calibration_module_path = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
        spec = importlib.util.spec_from_file_location("calibration_tracker", calibration_module_path)
        calibration_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(calibration_module)  # type: ignore

        tracker = calibration_module.CalibrationTracker(
            base_dir=Path(__file__).parent.parent
        )
        metrics = tracker.calculate_metrics()
        return jsonify(metrics.to_dict())
    except Exception as e:
        return jsonify({
            "error": str(e),
            "total_decisions": 0,
            "agreement_rate": 0.0,
            "status": "unknown",
            "message": "Failed to compute calibration metrics",
        }), 500


@app.route("/api/calibration/history")
def api_calibration_history():
    """
    API endpoint - get calibration history.

    Query parameters:
    - days: Number of days to look back (default: 30)
    """
    try:
        import importlib.util
        calibration_module_path = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
        spec = importlib.util.spec_from_file_location("calibration_tracker", calibration_module_path)
        calibration_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(calibration_module)  # type: ignore

        days = request.args.get("days", 30, type=int)

        tracker = calibration_module.CalibrationTracker(
            base_dir=Path(__file__).parent.parent
        )
        history = tracker.get_history(days=days)
        return jsonify({
            "history": [s.to_dict() for s in history],
            "days": days,
        })
    except Exception as e:
        return jsonify({"error": str(e), "history": []}), 500


@app.route("/api/calibration/disagreements")
def api_calibration_disagreements():
    """
    API endpoint - get calibration disagreements.

    Query parameters:
    - days: Number of days to look back (default: 90)
    - type: Filter by type (false_positive/false_negative)
    """
    try:
        import importlib.util
        from datetime import timedelta, timezone
        calibration_module_path = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
        spec = importlib.util.spec_from_file_location("calibration_tracker", calibration_module_path)
        calibration_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(calibration_module)  # type: ignore

        days = request.args.get("days", 90, type=int)
        disagreement_type = request.args.get("type")
        since = datetime.now(timezone.utc) - timedelta(days=days)

        tracker = calibration_module.CalibrationTracker(
            base_dir=Path(__file__).parent.parent
        )
        disagreements = tracker.get_disagreements(
            since=since,
            disagreement_type=disagreement_type
        )
        return jsonify({
            "disagreements": [d.to_dict() for d in disagreements],
            "days": days,
            "type": disagreement_type,
        })
    except Exception as e:
        return jsonify({"error": str(e), "disagreements": []}), 500


@app.route("/api/calibration/autonomous-check")
def api_autonomous_check():
    """
    API endpoint - check if autonomous mode is allowed.

    Returns eligibility status and requirements.
    """
    try:
        import importlib.util
        calibration_module_path = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
        spec = importlib.util.spec_from_file_location("calibration_tracker", calibration_module_path)
        calibration_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(calibration_module)  # type: ignore

        tracker = calibration_module.CalibrationTracker(
            base_dir=Path(__file__).parent.parent
        )
        result = tracker.check_autonomous_eligibility()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "eligible": False,
            "status": "unknown",
            "message": "Failed to check autonomous eligibility",
        }), 500


@app.route("/api/calibration/weekly-report")
def api_weekly_report():
    """
    API endpoint - get or generate weekly calibration report.

    Query parameters:
    - list: If 'true', list available reports
    - show: Report filename to retrieve (optional)
    """
    try:
        import importlib.util
        calibration_module_path = Path(__file__).parent.parent / "lib" / "calibration-tracker.py"
        spec = importlib.util.spec_from_file_location("calibration_tracker", calibration_module_path)
        calibration_module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(calibration_module)  # type: ignore

        tracker = calibration_module.CalibrationTracker(
            base_dir=Path(__file__).parent.parent
        )

        list_reports = request.args.get("list", "").lower() == "true"
        show_report = request.args.get("show")

        if list_reports:
            reports = tracker.list_weekly_reports()
            return jsonify({"reports": reports})

        if show_report:
            report = tracker.get_weekly_report(show_report)
            if not report:
                return jsonify({"error": f"Report not found: {show_report}"}), 404
            return jsonify(report.to_dict())

        # Generate new report
        report = tracker.generate_weekly_report()
        return jsonify(report.to_dict())
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to generate weekly report",
        }), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude-loop monitoring dashboard")
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to run on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Run in debug mode"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    args = parser.parse_args()

    print(f"Starting claude-loop dashboard on http://{args.host}:{args.port}")
    print(f"Runs directory: {RUNS_DIR}")

    app.run(host=args.host, port=args.port, debug=args.debug)
