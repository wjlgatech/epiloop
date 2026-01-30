#!/usr/bin/env python3
"""
report-generator.py - HTML Report Generator for claude-loop

Generates beautiful HTML reports from claude-loop run data including:
- Run summary with cost breakdown
- Story status and details
- Lessons learned from progress.txt
- Agent improvement suggestions

Usage:
    python lib/report-generator.py <run_directory>
    python lib/report-generator.py .claude-loop/runs/20260110_163000

Output:
    Creates report.html in the specified run directory
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any


def load_json_file(filepath: str) -> dict[str, Any] | None:
    """Load and parse a JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {filepath}: {e}", file=sys.stderr)
        return None


def load_text_file(filepath: str) -> str:
    """Load a text file."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def parse_progress_txt(content: str) -> list[dict[str, Any]]:
    """Parse progress.txt to extract iteration history."""
    iterations = []

    # Split by iteration headers
    iteration_pattern = r"### Iteration: (.+?)\n"
    sections = re.split(iteration_pattern, content)

    # Process each iteration section
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break

        timestamp = sections[i].strip()
        section_content = sections[i + 1]

        # Extract story info
        story_match = re.search(r"\*\*Story\*\*: (.+)", section_content)
        status_match = re.search(r"\*\*Status\*\*: (.+)", section_content)

        # Extract what was implemented
        impl_match = re.search(
            r"\*\*What was implemented\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        implementations = []
        if impl_match:
            implementations = [
                line.strip("- ").strip()
                for line in impl_match.group(1).strip().split("\n")
                if line.strip()
            ]

        # Extract files changed
        files_match = re.search(
            r"\*\*Files changed\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        files = []
        if files_match:
            files = [
                line.strip("- ").strip()
                for line in files_match.group(1).strip().split("\n")
                if line.strip()
            ]

        # Extract learnings
        learnings_match = re.search(
            r"\*\*Learnings for future iterations\*\*:\n((?:- .+\n?)+)",
            section_content
        )
        learnings = []
        if learnings_match:
            learnings = [
                line.strip("- ").strip()
                for line in learnings_match.group(1).strip().split("\n")
                if line.strip()
            ]

        iterations.append({
            "timestamp": timestamp,
            "story": story_match.group(1) if story_match else "Unknown",
            "status": status_match.group(1) if status_match else "Unknown",
            "implementations": implementations,
            "files": files,
            "learnings": learnings,
        })

    return iterations


def format_cost(cost: float) -> str:
    """Format cost for display."""
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_tokens(tokens: int) -> str:
    """Format token count for display."""
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1000000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1000000:.2f}M"


def format_duration(duration_ms: int) -> str:
    """Format duration for display."""
    duration_s = duration_ms // 1000
    if duration_s < 60:
        return f"{duration_s}s"
    minutes = duration_s // 60
    seconds = duration_s % 60
    return f"{minutes}m {seconds}s"


def get_status_class(status: str) -> str:
    """Get CSS class for status."""
    status_lower = status.lower()
    if status_lower in ("complete", "completed"):
        return "success"
    elif status_lower in ("failed", "error"):
        return "error"
    elif status_lower == "blocked":
        return "warning"
    return "info"


def get_priority_class(priority: str) -> str:
    """Get CSS class for priority."""
    priority_lower = priority.lower()
    if priority_lower == "high":
        return "error"
    elif priority_lower == "medium":
        return "warning"
    return "info"


def run_agent_improver(run_dir: str) -> dict[str, Any] | None:
    """Run agent-improver.py and get improvement suggestions."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    improver_script = os.path.join(script_dir, "agent-improver.py")

    if not os.path.exists(improver_script):
        print(f"Warning: agent-improver.py not found at {improver_script}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            [sys.executable, improver_script, run_dir],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Warning: agent-improver.py failed: {result.stderr}", file=sys.stderr)
            return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"Warning: Could not run agent-improver.py: {e}", file=sys.stderr)
        return None


def generate_html_report(
    metrics: dict[str, Any] | None,
    summary: dict[str, Any] | None,
    progress_iterations: list[dict[str, Any]],
    prd_data: dict[str, Any] | None,
    improvements: dict[str, Any] | None = None,
) -> str:
    """Generate the HTML report content."""

    # Extract data with defaults
    session_id = summary.get("session_id", "Unknown") if summary else "Unknown"
    started_at = summary.get("started_at", "") if summary else ""
    completed_at = summary.get("completed_at", "") if summary else ""

    # Stories summary
    stories_info = summary.get("stories", {}) if summary else {}
    total_stories = stories_info.get("total", 0)
    completed_stories = stories_info.get("completed", 0)
    failed_stories = stories_info.get("failed", 0)

    # Token and cost info
    tokens_info = summary.get("tokens", {}) if summary else {}
    total_tokens_in = tokens_info.get("input", 0)
    total_tokens_out = tokens_info.get("output", 0)

    cost_info = summary.get("cost", {}) if summary else {}
    total_cost = cost_info.get("total_usd", 0)
    input_cost = cost_info.get("input_usd", 0)
    output_cost = cost_info.get("output_usd", 0)

    # Duration info
    duration_info = summary.get("duration", {}) if summary else {}
    api_duration = duration_info.get("api_formatted", "0s")
    wall_duration = duration_info.get("wall_formatted", "0s")

    # Model usage info
    model_usage = summary.get("model_usage", {}) if summary else {}
    haiku_count = model_usage.get("haiku", 0)
    sonnet_count = model_usage.get("sonnet", 0)
    opus_count = model_usage.get("opus", 0)

    # Cache info
    cache_info = summary.get("cache", {}) if summary else {}
    cache_hits = cache_info.get("hits", 0)
    cache_misses = cache_info.get("misses", 0)
    cache_hit_rate = cache_info.get("hit_rate", 0)
    cache_saved_tokens = cache_info.get("saved_tokens_estimate", 0)

    # Parallel execution info
    parallel_info = summary.get("parallel", {}) if summary else {}
    parallel_enabled = parallel_info.get("enabled", False)
    parallel_batches = parallel_info.get("batches", 0)
    parallel_workers = parallel_info.get("workers_used", 0)
    parallel_max_concurrent = parallel_info.get("max_concurrent", 0)
    parallel_time_formatted = parallel_info.get("parallel_formatted", "0s")
    sequential_time_formatted = parallel_info.get("sequential_formatted", "0s")
    time_saved_formatted = parallel_info.get("time_saved_formatted", "0s")
    speedup_factor = parallel_info.get("speedup_factor", 1.0)

    # Cost savings info
    opus_baseline = cost_info.get("opus_baseline_usd", 0)
    cost_savings = cost_info.get("savings_usd", 0)
    savings_percent = cost_info.get("savings_percent", 0)

    # Get iterations from metrics
    iterations = metrics.get("iterations", []) if metrics else []

    # Get user stories from PRD
    user_stories = prd_data.get("userStories", []) if prd_data else []
    project_name = prd_data.get("project", "Unknown Project") if prd_data else "Unknown Project"

    # Collect all learnings from progress
    all_learnings = []
    for iteration in progress_iterations:
        all_learnings.extend(iteration.get("learnings", []))

    # Generate iteration rows
    iteration_rows = ""
    for i, it in enumerate(iterations):
        status_class = get_status_class(it.get("status", "unknown"))
        iteration_rows += f"""
        <tr>
            <td>{i + 1}</td>
            <td>{it.get("story_id", "N/A")}</td>
            <td class="{status_class}">{it.get("status", "unknown").title()}</td>
            <td>{format_tokens(it.get("tokens_in", 0))}</td>
            <td>{format_tokens(it.get("tokens_out", 0))}</td>
            <td>{format_cost(it.get("cost_usd", 0))}</td>
            <td>{format_duration(it.get("duration_ms", 0))}</td>
            <td>{it.get("agents_used", "-") or "-"}</td>
        </tr>
        """

    # Generate story rows
    story_rows = ""
    for story in user_stories:
        status = "Complete" if story.get("passes") else "Pending"
        status_class = "success" if story.get("passes") else "warning"
        criteria_list = "<br>".join([f"- {c}" for c in story.get("acceptanceCriteria", [])])
        story_rows += f"""
        <tr>
            <td>{story.get("id", "N/A")}</td>
            <td>{story.get("title", "N/A")}</td>
            <td class="{status_class}">{status}</td>
            <td>{story.get("priority", "-")}</td>
            <td class="criteria">{criteria_list}</td>
        </tr>
        """

    # Generate learnings list
    learnings_html = ""
    if all_learnings:
        for learning in all_learnings:
            learnings_html += f"<li>{learning}</li>\n"
    else:
        learnings_html = "<li>No learnings recorded yet.</li>"

    # Generate progress timeline
    progress_html = ""
    for iteration in progress_iterations:
        impl_items = "".join([f"<li>{impl}</li>" for impl in iteration.get("implementations", [])])
        file_items = "".join([f"<li><code>{f}</code></li>" for f in iteration.get("files", [])])

        progress_html += f"""
        <div class="timeline-item">
            <div class="timeline-header">
                <span class="timeline-time">{iteration.get("timestamp", "")}</span>
                <span class="badge {get_status_class(iteration.get("status", ""))}">{iteration.get("status", "")}</span>
            </div>
            <h4>{iteration.get("story", "Unknown Story")}</h4>
            {"<p><strong>Implemented:</strong></p><ul>" + impl_items + "</ul>" if impl_items else ""}
            {"<p><strong>Files Changed:</strong></p><ul>" + file_items + "</ul>" if file_items else ""}
        </div>
        """

    if not progress_html:
        progress_html = "<p>No iteration history available.</p>"

    # Generate improvement suggestions section
    improvements_html = ""
    if improvements and improvements.get("improvement_suggestions"):
        suggestions = improvements.get("improvement_suggestions", [])
        for suggestion in suggestions:
            action_items = "".join([
                f"<li>{item}</li>"
                for item in suggestion.get("action_items", [])
            ])
            priority_class = get_priority_class(suggestion.get("priority", "low"))
            improvements_html += f"""
            <div class="improvement-card">
                <div class="improvement-header">
                    <span class="improvement-id">{suggestion.get("id", "")}</span>
                    <span class="badge {priority_class}">{suggestion.get("priority", "").upper()}</span>
                    <span class="improvement-category">{suggestion.get("category", "").title()}</span>
                </div>
                <h4>{suggestion.get("title", "")}</h4>
                <p>{suggestion.get("description", "")}</p>
                {"<ul class='action-items'>" + action_items + "</ul>" if action_items else ""}
            </div>
            """
    else:
        improvements_html = "<p class='no-improvements'>No improvement suggestions - the run looks good!</p>"

    # Generate AGENTS.md updates section
    agents_updates_html = ""
    if improvements and improvements.get("agents_md_updates"):
        updates = improvements.get("agents_md_updates", [])
        for update in updates[:5]:  # Limit to 5
            agents_updates_html += f"""
            <div class="agents-update">
                <span class="update-section">{update.get("suggested_section", "")}</span>
                <p>{update.get("content", "")}</p>
            </div>
            """
    else:
        agents_updates_html = "<p>No AGENTS.md updates suggested.</p>"

    # Calculate completion percentage
    completion_pct = (completed_stories / total_stories * 100) if total_stories > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude-Loop Report - {session_id}</title>
    <style>
        :root {{
            --primary: #6366f1;
            --primary-light: #818cf8;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --info: #3b82f6;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            color: white;
            padding: 2rem;
            border-radius: 1rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}

        header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        header p {{
            opacity: 0.9;
        }}

        .meta {{
            display: flex;
            gap: 2rem;
            margin-top: 1rem;
            font-size: 0.875rem;
            opacity: 0.9;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .card {{
            background: var(--card-bg);
            border-radius: 0.75rem;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }}

        .card h3 {{
            font-size: 0.875rem;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            letter-spacing: 0.05em;
        }}

        .card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .card .subtext {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        .section {{
            background: var(--card-bg);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }}

        .section h2 {{
            font-size: 1.25rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        tr:hover {{
            background: var(--bg);
        }}

        .success {{ color: var(--success); }}
        .warning {{ color: var(--warning); }}
        .error {{ color: var(--error); }}
        .info {{ color: var(--info); }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge.success {{ background: #d1fae5; color: #065f46; }}
        .badge.warning {{ background: #fef3c7; color: #92400e; }}
        .badge.error {{ background: #fee2e2; color: #991b1b; }}
        .badge.info {{ background: #dbeafe; color: #1e40af; }}

        .progress-bar {{
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }}

        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--success), #34d399);
            transition: width 0.3s ease;
        }}

        .cost-breakdown {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-top: 1rem;
        }}

        .cost-item {{
            text-align: center;
            padding: 1rem;
            background: var(--bg);
            border-radius: 0.5rem;
        }}

        .cost-item .label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .cost-item .amount {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .timeline {{
            position: relative;
            padding-left: 2rem;
        }}

        .timeline::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border);
        }}

        .timeline-item {{
            position: relative;
            padding-bottom: 1.5rem;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
        }}

        .timeline-item:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}

        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -2rem;
            top: 0.25rem;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--primary);
            border: 2px solid white;
            box-shadow: 0 0 0 2px var(--primary);
            transform: translateX(-5px);
        }}

        .timeline-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}

        .timeline-time {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .timeline-item h4 {{
            margin-bottom: 0.5rem;
        }}

        .timeline-item ul {{
            margin-left: 1.5rem;
            margin-top: 0.5rem;
        }}

        .timeline-item li {{
            margin-bottom: 0.25rem;
        }}

        .learnings-list {{
            list-style: none;
            padding: 0;
        }}

        .learnings-list li {{
            padding: 0.75rem 1rem;
            background: var(--bg);
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
            border-left: 3px solid var(--primary);
        }}

        .criteria {{
            font-size: 0.75rem;
            line-height: 1.4;
        }}

        /* Improvement suggestions styles */
        .improvement-card {{
            background: var(--bg);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 4px solid var(--primary);
        }}

        .improvement-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }}

        .improvement-id {{
            font-family: monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
            background: var(--card-bg);
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
        }}

        .improvement-category {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .improvement-card h4 {{
            margin-bottom: 0.5rem;
            color: var(--text);
        }}

        .improvement-card p {{
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }}

        .action-items {{
            margin-left: 1.5rem;
            margin-top: 0.5rem;
        }}

        .action-items li {{
            font-size: 0.875rem;
            margin-bottom: 0.25rem;
            color: var(--text);
        }}

        .no-improvements {{
            color: var(--success);
            font-style: italic;
        }}

        .agents-update {{
            background: var(--bg);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }}

        .update-section {{
            font-size: 0.75rem;
            color: var(--primary);
            text-transform: uppercase;
            font-weight: 600;
        }}

        .agents-update p {{
            margin-top: 0.5rem;
            font-size: 0.875rem;
        }}

        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            .meta {{
                flex-direction: column;
                gap: 0.5rem;
            }}

            .cost-breakdown {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Claude-Loop Run Report</h1>
            <p>{project_name}</p>
            <div class="meta">
                <span>Session: {session_id}</span>
                <span>Started: {started_at}</span>
                <span>Completed: {completed_at}</span>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <h3>Stories Completed</h3>
                <div class="value">{completed_stories}/{total_stories}</div>
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: {completion_pct:.0f}%"></div>
                </div>
                <div class="subtext">{completion_pct:.1f}% complete</div>
            </div>

            <div class="card">
                <h3>Total Cost</h3>
                <div class="value">{format_cost(total_cost)}</div>
                <div class="subtext">{format_tokens(total_tokens_in)} in / {format_tokens(total_tokens_out)} out</div>
            </div>

            <div class="card">
                <h3>Duration</h3>
                <div class="value">{wall_duration}</div>
                <div class="subtext">API time: {api_duration}</div>
            </div>

            <div class="card">
                <h3>Iterations</h3>
                <div class="value">{len(iterations)}</div>
                <div class="subtext">{failed_stories} failed</div>
            </div>
        </div>

        <div class="section">
            <h2>Cost Breakdown</h2>
            <div class="cost-breakdown">
                <div class="cost-item">
                    <div class="label">Input Tokens</div>
                    <div class="amount">{format_cost(input_cost)}</div>
                    <div class="subtext">{format_tokens(total_tokens_in)} tokens</div>
                </div>
                <div class="cost-item">
                    <div class="label">Output Tokens</div>
                    <div class="amount">{format_cost(output_cost)}</div>
                    <div class="subtext">{format_tokens(total_tokens_out)} tokens</div>
                </div>
                <div class="cost-item">
                    <div class="label">Total Cost</div>
                    <div class="amount">{format_cost(total_cost)}</div>
                    <div class="subtext">$15/M in, $75/M out</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Optimization Stats</h2>
            <div class="grid">
                <div class="card">
                    <h3>Model Usage</h3>
                    <div class="value">{haiku_count + sonnet_count + opus_count}</div>
                    <div class="subtext">
                        Haiku: {haiku_count} | Sonnet: {sonnet_count} | Opus: {opus_count}
                    </div>
                </div>
                <div class="card">
                    <h3>Cost Savings</h3>
                    <div class="value">{format_cost(cost_savings)}</div>
                    <div class="subtext">
                        {savings_percent:.1f}% vs all-Opus baseline ({format_cost(opus_baseline)})
                    </div>
                </div>
                <div class="card">
                    <h3>Cache Performance</h3>
                    <div class="value">{cache_hit_rate:.1f}%</div>
                    <div class="subtext">
                        {cache_hits} hits / {cache_hits + cache_misses} total | {format_tokens(cache_saved_tokens)} tokens saved
                    </div>
                </div>
                {"<div class='card'><h3>Parallel Speedup</h3><div class='value'>" + f"{speedup_factor:.1f}x" + "</div><div class='subtext'>" + f"{parallel_batches} batches | {parallel_workers} workers (max {parallel_max_concurrent} concurrent)" + "</div></div>" if parallel_enabled else ""}
            </div>
            {"<div class='cost-breakdown'><div class='cost-item'><div class='label'>Sequential Time (Est.)</div><div class='amount'>" + sequential_time_formatted + "</div></div><div class='cost-item'><div class='label'>Parallel Time</div><div class='amount'>" + parallel_time_formatted + "</div></div><div class='cost-item'><div class='label'>Time Saved</div><div class='amount'>" + time_saved_formatted + "</div></div></div>" if parallel_enabled else ""}
        </div>

        <div class="section">
            <h2>Iteration Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Story</th>
                        <th>Status</th>
                        <th>Tokens In</th>
                        <th>Tokens Out</th>
                        <th>Cost</th>
                        <th>Duration</th>
                        <th>Agents</th>
                    </tr>
                </thead>
                <tbody>
                    {iteration_rows if iteration_rows else '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No iteration data available</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>User Stories</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Status</th>
                        <th>Priority</th>
                        <th>Acceptance Criteria</th>
                    </tr>
                </thead>
                <tbody>
                    {story_rows if story_rows else '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No stories defined</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Lessons Learned</h2>
            <ul class="learnings-list">
                {learnings_html}
            </ul>
        </div>

        <div class="section">
            <h2>Agent Improvement Suggestions</h2>
            {improvements_html}
        </div>

        <div class="section">
            <h2>Suggested AGENTS.md Updates</h2>
            {agents_updates_html}
        </div>

        <div class="section">
            <h2>Implementation Timeline</h2>
            <div class="timeline">
                {progress_html}
            </div>
        </div>

        <footer>
            <p>Generated by claude-loop report generator</p>
            <p>Report created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </footer>
    </div>
</body>
</html>
"""
    return html


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python lib/report-generator.py <run_directory>")
        print("Example: python lib/report-generator.py .claude-loop/runs/20260110_163000")
        sys.exit(1)

    run_dir = sys.argv[1]

    if not os.path.isdir(run_dir):
        print(f"Error: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    # Load data files
    metrics_file = os.path.join(run_dir, "metrics.json")
    summary_file = os.path.join(run_dir, "summary.json")

    # Look for prd.json and progress.txt in the project root
    # Assuming run_dir is like .claude-loop/runs/{timestamp}/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(run_dir)))
    if not project_root:
        project_root = "."

    prd_file = os.path.join(project_root, "prd.json")
    progress_file = os.path.join(project_root, "progress.txt")

    # If not found in computed root, try current directory
    if not os.path.exists(prd_file):
        prd_file = "prd.json"
    if not os.path.exists(progress_file):
        progress_file = "progress.txt"

    print(f"Loading metrics from: {metrics_file}")
    print(f"Loading summary from: {summary_file}")
    print(f"Loading PRD from: {prd_file}")
    print(f"Loading progress from: {progress_file}")

    metrics = load_json_file(metrics_file)
    summary = load_json_file(summary_file)
    prd_data = load_json_file(prd_file)
    progress_content = load_text_file(progress_file)

    # Parse progress.txt
    progress_iterations = parse_progress_txt(progress_content)

    # Run agent improver to get improvement suggestions
    print("Running agent improver analysis...")
    improvements = run_agent_improver(run_dir)

    # Generate report
    html_content = generate_html_report(
        metrics=metrics,
        improvements=improvements,
        summary=summary,
        progress_iterations=progress_iterations,
        prd_data=prd_data,
    )

    # Save report
    report_file = os.path.join(run_dir, "report.html")
    with open(report_file, "w") as f:
        f.write(html_content)

    print(f"\nReport generated: {report_file}")
    return report_file


if __name__ == "__main__":
    main()
