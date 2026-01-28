#!/usr/bin/env python3
"""
Dashboard API
=============

Core API implementation for reading metrics and execution data from
.claude-loop/runs/ directory and providing structured data to the Flask server.

Data Sources:
- .claude-loop/runs/{timestamp}/metrics.json - Per-iteration metrics
- .claude-loop/runs/{timestamp}/summary.json - Run summary
- prd.json - Current PRD with story status
- progress.txt - Iteration logs
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import glob


class DashboardAPI:
    """Core API for dashboard backend."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize Dashboard API.

        Args:
            base_dir: Base directory for claude-loop (default: current working directory)
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.runs_dir = self.base_dir / ".claude-loop" / "runs"
        self.prd_path = self.base_dir / "prd.json"
        self.progress_path = self.base_dir / "progress.txt"

    # ==========================================================================
    # Current Execution Status
    # ==========================================================================

    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current execution status.

        Returns:
            Dictionary with current status including:
            - is_running: Whether execution is currently running
            - current_story: Current story being executed
            - progress_pct: Overall progress percentage
            - elapsed_time: Elapsed time in seconds
            - estimated_remaining: Estimated remaining time
            - last_update: Timestamp of last update
        """
        # Find most recent run
        recent_run = self._get_most_recent_run()
        if not recent_run:
            return {
                "is_running": False,
                "message": "No active execution",
                "last_update": datetime.utcnow().isoformat() + "Z"
            }

        # Load metrics
        metrics_file = recent_run / "metrics.json"
        if not metrics_file.exists():
            return {
                "is_running": False,
                "message": "No metrics available",
                "last_update": datetime.utcnow().isoformat() + "Z"
            }

        with open(metrics_file) as f:
            metrics = json.load(f)

        # Load PRD for story count
        prd = self._load_prd()
        total_stories = len(prd.get("userStories", [])) if prd else 0
        completed_stories = len([s for s in prd.get("userStories", []) if s.get("passes")]) if prd else 0

        # Calculate progress
        progress_pct = (completed_stories / total_stories * 100) if total_stories > 0 else 0

        # Get current story
        current_story = None
        if metrics.get("iterations"):
            last_iteration = metrics["iterations"][-1]
            current_story = {
                "id": last_iteration.get("story_id"),
                "status": last_iteration.get("status"),
                "elapsed_ms": last_iteration.get("elapsed_ms")
            }

        # Check if running (recent update within last 60 seconds)
        last_update_time = datetime.fromisoformat(metrics.get("last_update", "1970-01-01T00:00:00Z").replace("Z", ""))
        is_running = (datetime.utcnow() - last_update_time).total_seconds() < 60

        return {
            "is_running": is_running,
            "run_id": recent_run.name,
            "current_story": current_story,
            "progress_pct": round(progress_pct, 1),
            "completed_stories": completed_stories,
            "total_stories": total_stories,
            "elapsed_time": metrics.get("elapsed_time_s", 0),
            "estimated_remaining": self._estimate_remaining_time(metrics, total_stories, completed_stories),
            "cost_so_far": metrics.get("total_cost", 0),
            "last_update": metrics.get("last_update", datetime.utcnow().isoformat() + "Z")
        }

    def _estimate_remaining_time(self, metrics: Dict, total_stories: int, completed_stories: int) -> Optional[int]:
        """Estimate remaining time based on average iteration time."""
        if not metrics.get("iterations") or completed_stories == 0:
            return None

        avg_time_per_story = metrics.get("elapsed_time_s", 0) / completed_stories
        remaining_stories = total_stories - completed_stories
        return int(avg_time_per_story * remaining_stories)

    # ==========================================================================
    # Stories
    # ==========================================================================

    def get_stories(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all stories with their status.

        Args:
            run_id: Optional run ID to get stories for specific run

        Returns:
            Dictionary with stories array and metadata
        """
        prd = self._load_prd()
        if not prd:
            return {"stories": [], "total": 0}

        stories = []
        for story in prd.get("userStories", []):
            stories.append({
                "id": story.get("id"),
                "title": story.get("title"),
                "description": story.get("description"),
                "priority": story.get("priority"),
                "status": "completed" if story.get("passes") else "pending",
                "notes": story.get("notes", ""),
                "estimatedComplexity": story.get("estimatedComplexity"),
                "dependencies": story.get("dependencies", [])
            })

        return {
            "stories": stories,
            "total": len(stories),
            "completed": len([s for s in stories if s["status"] == "completed"]),
            "pending": len([s for s in stories if s["status"] == "pending"])
        }

    # ==========================================================================
    # Logs
    # ==========================================================================

    def get_logs(self, run_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Get execution logs.

        Args:
            run_id: Optional run ID to get logs for
            limit: Maximum number of log entries to return
            offset: Number of entries to skip

        Returns:
            Dictionary with logs array and metadata
        """
        # Read progress.txt
        if not self.progress_path.exists():
            return {"logs": [], "total": 0, "limit": limit, "offset": offset}

        with open(self.progress_path) as f:
            content = f.read()

        # Parse iterations from progress.txt
        logs = []
        current_iteration = None

        for line in content.split("\n"):
            if line.startswith("### Iteration:"):
                if current_iteration:
                    logs.append(current_iteration)

                timestamp_str = line.split("Iteration:")[1].strip()
                current_iteration = {
                    "timestamp": timestamp_str,
                    "lines": []
                }
            elif current_iteration:
                current_iteration["lines"].append(line)

        # Add last iteration
        if current_iteration:
            logs.append(current_iteration)

        # Apply pagination
        total = len(logs)
        logs = logs[offset:offset + limit]

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    # ==========================================================================
    # Metrics
    # ==========================================================================

    def get_metrics(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution metrics.

        Args:
            run_id: Optional run ID to get metrics for

        Returns:
            Dictionary with metrics data
        """
        if run_id:
            metrics_file = self.runs_dir / run_id / "metrics.json"
        else:
            recent_run = self._get_most_recent_run()
            if not recent_run:
                return {"error": "No metrics available"}
            metrics_file = recent_run / "metrics.json"

        if not metrics_file.exists():
            return {"error": "Metrics file not found"}

        with open(metrics_file) as f:
            metrics = json.load(f)

        return metrics

    # ==========================================================================
    # History
    # ==========================================================================

    def get_history(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Get historical runs.

        Args:
            limit: Maximum number of runs to return
            offset: Number of runs to skip

        Returns:
            Dictionary with runs array and metadata
        """
        runs = self._get_all_runs()

        # Sort by timestamp (most recent first)
        runs.sort(key=lambda r: r["timestamp"], reverse=True)

        # Apply pagination
        total = len(runs)
        runs = runs[offset:offset + limit]

        return {
            "runs": runs,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    def get_all_runs(self) -> List[Dict[str, Any]]:
        """Get list of all runs."""
        return self._get_all_runs()

    def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific run.

        Args:
            run_id: Run ID (timestamp directory name)

        Returns:
            Dictionary with run details or None if not found
        """
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            return None

        # Load summary
        summary_file = run_dir / "summary.json"
        summary = {}
        if summary_file.exists():
            with open(summary_file) as f:
                summary = json.load(f)

        # Load metrics
        metrics_file = run_dir / "metrics.json"
        metrics = {}
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)

        return {
            "run_id": run_id,
            "timestamp": run_id,
            "summary": summary,
            "metrics": metrics
        }

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _get_most_recent_run(self) -> Optional[Path]:
        """Get most recent run directory."""
        if not self.runs_dir.exists():
            return None

        run_dirs = [d for d in self.runs_dir.iterdir() if d.is_dir()]
        if not run_dirs:
            return None

        # Sort by name (timestamp) descending
        run_dirs.sort(reverse=True)
        return run_dirs[0]

    def _get_all_runs(self) -> List[Dict[str, Any]]:
        """Get list of all runs with summary information."""
        if not self.runs_dir.exists():
            return []

        runs = []
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue

            # Load summary if available
            summary_file = run_dir / "summary.json"
            if summary_file.exists():
                with open(summary_file) as f:
                    summary = json.load(f)

                runs.append({
                    "run_id": run_dir.name,
                    "timestamp": run_dir.name,
                    "total_cost": summary.get("total_cost", 0),
                    "total_iterations": summary.get("total_iterations", 0),
                    "success_count": summary.get("success_count", 0),
                    "failure_count": summary.get("failure_count", 0),
                    "elapsed_time_s": summary.get("elapsed_time_s", 0)
                })
            else:
                # Minimal info without summary
                runs.append({
                    "run_id": run_dir.name,
                    "timestamp": run_dir.name
                })

        return runs

    def _load_prd(self) -> Optional[Dict[str, Any]]:
        """Load PRD file."""
        if not self.prd_path.exists():
            return None

        with open(self.prd_path) as f:
            return json.load(f)
