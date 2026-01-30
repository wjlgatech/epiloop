#!/usr/bin/env python3
"""
capability-inventory.py - Capability Inventory Tracker for claude-loop

Tracks and inventories claude-loop's current capabilities, including tools,
MCP servers, agents, and skills. Enables predictive gap detection by matching
task requirements against available capabilities.

Features:
- Define capability taxonomy: categories, subcategories, skills
- Auto-discover capabilities from MCP servers, tools, agents
- Track capability status: available, limited, unavailable
- Map each capability to required dependencies
- Check task requirements against available capabilities

Usage:
    python lib/capability-inventory.py list
    python lib/capability-inventory.py list --category <category>
    python lib/capability-inventory.py check <task_description>
    python lib/capability-inventory.py discover
    python lib/capability-inventory.py show <capability_id>
    python lib/capability-inventory.py status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Capability Taxonomy
# ============================================================================

class CapabilityCategory(Enum):
    """Top-level capability categories."""

    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    FILE_OPERATIONS = "file_operations"
    SHELL_EXECUTION = "shell_execution"
    UI_AUTOMATION = "ui_automation"
    NETWORK_OPERATIONS = "network_operations"
    DATA_PROCESSING = "data_processing"
    TESTING = "testing"
    VERSION_CONTROL = "version_control"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    REASONING = "reasoning"
    COMMUNICATION = "communication"


class CapabilityStatus(Enum):
    """Status of a capability."""

    AVAILABLE = "available"        # Fully functional
    LIMITED = "limited"            # Partially available (e.g., rate limited)
    UNAVAILABLE = "unavailable"    # Not available (missing dependency)
    UNKNOWN = "unknown"            # Status not yet determined


# Subcategories for each category
SUBCATEGORIES: dict[str, list[str]] = {
    CapabilityCategory.CODE_GENERATION.value: [
        "python",
        "javascript",
        "typescript",
        "rust",
        "go",
        "shell_script",
        "sql",
        "html_css",
        "markdown",
        "yaml_json",
    ],
    CapabilityCategory.CODE_ANALYSIS.value: [
        "static_analysis",
        "linting",
        "type_checking",
        "code_review",
        "refactoring",
        "dependency_analysis",
        "complexity_analysis",
        "security_scan",
    ],
    CapabilityCategory.FILE_OPERATIONS.value: [
        "read",
        "write",
        "edit",
        "search",
        "glob",
        "create",
        "delete",
        "move",
        "copy",
        "permission",
    ],
    CapabilityCategory.SHELL_EXECUTION.value: [
        "command",
        "script",
        "background",
        "timeout",
        "environment",
        "pipe",
    ],
    CapabilityCategory.UI_AUTOMATION.value: [
        "screenshot",
        "click",
        "type",
        "scroll",
        "element_detection",
        "window_management",
        "form_filling",
    ],
    CapabilityCategory.NETWORK_OPERATIONS.value: [
        "http_request",
        "websocket",
        "download",
        "upload",
        "api_call",
        "web_search",
    ],
    CapabilityCategory.DATA_PROCESSING.value: [
        "json_parsing",
        "xml_parsing",
        "csv_processing",
        "text_extraction",
        "data_transformation",
        "validation",
    ],
    CapabilityCategory.TESTING.value: [
        "unit_testing",
        "integration_testing",
        "e2e_testing",
        "test_generation",
        "coverage_analysis",
        "mocking",
    ],
    CapabilityCategory.VERSION_CONTROL.value: [
        "git_operations",
        "branch_management",
        "commit",
        "push_pull",
        "merge",
        "pr_management",
    ],
    CapabilityCategory.DOCUMENTATION.value: [
        "docstring",
        "readme",
        "api_docs",
        "comments",
        "changelog",
    ],
    CapabilityCategory.SECURITY.value: [
        "vulnerability_scan",
        "secret_detection",
        "permission_check",
        "input_validation",
        "encryption",
    ],
    CapabilityCategory.REASONING.value: [
        "planning",
        "decomposition",
        "root_cause_analysis",
        "decision_making",
        "problem_solving",
    ],
    CapabilityCategory.COMMUNICATION.value: [
        "user_query",
        "notification",
        "progress_report",
        "error_reporting",
    ],
}


# Skill keywords for capability matching
SKILL_KEYWORDS: dict[str, list[str]] = {
    "python": ["python", "py", "pip", "poetry", "virtualenv", "pytest", "django", "flask", "fastapi"],
    "javascript": ["javascript", "js", "node", "npm", "yarn", "react", "vue", "angular"],
    "typescript": ["typescript", "ts", "tsc", "tsx", "type"],
    "rust": ["rust", "cargo", "crate", "rustc"],
    "go": ["golang", "go mod", "go build"],
    "shell_script": ["bash", "sh", "shell", "zsh", "script"],
    "sql": ["sql", "database", "query", "postgresql", "mysql", "sqlite"],
    "static_analysis": ["lint", "analyze", "pyright", "eslint", "pylint", "ruff"],
    "type_checking": ["type", "pyright", "mypy", "typescript", "typecheck"],
    "screenshot": ["screenshot", "capture", "screen", "display", "visual"],
    "click": ["click", "button", "element", "ui", "gui"],
    "type": ["type", "input", "keyboard", "text entry"],
    "element_detection": ["element", "locate", "find", "detect", "identify"],
    "http_request": ["http", "https", "request", "fetch", "api", "rest"],
    "web_search": ["search", "google", "web", "internet"],
    "git_operations": ["git", "commit", "branch", "merge", "push", "pull", "clone"],
    "test_generation": ["test", "unittest", "pytest", "jest", "mocha"],
    "vulnerability_scan": ["security", "vulnerability", "cve", "owasp", "audit"],
    "secret_detection": ["secret", "password", "api key", "credential", "token"],
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Capability:
    """A single capability tracked in the inventory."""

    capability_id: str
    name: str
    category: str
    subcategory: str
    description: str
    status: str  # available, limited, unavailable, unknown
    source: str  # tool, mcp_server, agent, skill, builtin
    source_name: str  # Name of the specific source
    dependencies: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    version: str = ""
    last_checked: str = ""
    limitations: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "status": self.status,
            "source": self.source,
            "source_name": self.source_name,
            "dependencies": self.dependencies,
            "keywords": self.keywords,
            "version": self.version,
            "last_checked": self.last_checked,
            "limitations": self.limitations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Capability:
        return cls(
            capability_id=data.get("capability_id", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            description=data.get("description", ""),
            status=data.get("status", CapabilityStatus.UNKNOWN.value),
            source=data.get("source", ""),
            source_name=data.get("source_name", ""),
            dependencies=data.get("dependencies", []),
            keywords=data.get("keywords", []),
            version=data.get("version", ""),
            last_checked=data.get("last_checked", ""),
            limitations=data.get("limitations", ""),
        )


@dataclass
class TaskRequirement:
    """A requirement extracted from a task description."""

    category: str
    subcategory: str
    keywords: list[str]
    confidence: float  # How confident we are this is needed


@dataclass
class CapabilityCheckResult:
    """Result of checking capabilities against task requirements."""

    task_description: str
    requirements: list[TaskRequirement]
    available_capabilities: list[Capability]
    missing_capabilities: list[TaskRequirement]
    limited_capabilities: list[Capability]
    confidence: float
    can_complete: bool
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_description": self.task_description,
            "requirements": [
                {
                    "category": r.category,
                    "subcategory": r.subcategory,
                    "keywords": r.keywords,
                    "confidence": round(r.confidence, 3),
                }
                for r in self.requirements
            ],
            "available_capabilities": [c.to_dict() for c in self.available_capabilities],
            "missing_capabilities": [
                {
                    "category": m.category,
                    "subcategory": m.subcategory,
                    "keywords": m.keywords,
                }
                for m in self.missing_capabilities
            ],
            "limited_capabilities": [c.to_dict() for c in self.limited_capabilities],
            "confidence": round(self.confidence, 3),
            "can_complete": self.can_complete,
            "suggestions": self.suggestions,
        }


# ============================================================================
# Capability Inventory
# ============================================================================

class CapabilityInventory:
    """
    Tracks and manages claude-loop's capability inventory.

    Discovers capabilities from:
    - Built-in tools (Read, Write, Edit, Bash, Glob, Grep)
    - MCP servers (configured in config.yaml)
    - Agents (from agents/ directory)
    - Skills (from skills/ directory)
    """

    # Built-in tools from Claude Code
    BUILTIN_TOOLS = {
        "Read": {
            "category": CapabilityCategory.FILE_OPERATIONS.value,
            "subcategory": "read",
            "description": "Read file contents from the filesystem",
            "keywords": ["read", "file", "content", "view", "open"],
        },
        "Write": {
            "category": CapabilityCategory.FILE_OPERATIONS.value,
            "subcategory": "write",
            "description": "Write content to a file (creates or overwrites)",
            "keywords": ["write", "file", "create", "save", "output"],
        },
        "Edit": {
            "category": CapabilityCategory.FILE_OPERATIONS.value,
            "subcategory": "edit",
            "description": "Make targeted edits to files using string replacement",
            "keywords": ["edit", "replace", "modify", "change", "update"],
        },
        "Bash": {
            "category": CapabilityCategory.SHELL_EXECUTION.value,
            "subcategory": "command",
            "description": "Execute shell commands in a bash environment",
            "keywords": ["bash", "shell", "command", "execute", "run", "terminal"],
        },
        "Glob": {
            "category": CapabilityCategory.FILE_OPERATIONS.value,
            "subcategory": "glob",
            "description": "Find files matching glob patterns",
            "keywords": ["glob", "pattern", "find", "search", "files", "match"],
        },
        "Grep": {
            "category": CapabilityCategory.FILE_OPERATIONS.value,
            "subcategory": "search",
            "description": "Search file contents using regex patterns",
            "keywords": ["grep", "search", "regex", "pattern", "content", "find"],
        },
        "Task": {
            "category": CapabilityCategory.REASONING.value,
            "subcategory": "decomposition",
            "description": "Create and manage sub-tasks for complex operations",
            "keywords": ["task", "subtask", "agent", "parallel", "delegate"],
        },
        "WebSearch": {
            "category": CapabilityCategory.NETWORK_OPERATIONS.value,
            "subcategory": "web_search",
            "description": "Search the web for information",
            "keywords": ["search", "web", "internet", "google", "query"],
        },
        "mcp__ide__getDiagnostics": {
            "category": CapabilityCategory.CODE_ANALYSIS.value,
            "subcategory": "static_analysis",
            "description": "Get IDE diagnostics (type errors, lint warnings)",
            "keywords": ["diagnostics", "ide", "lint", "type", "error", "warning"],
        },
        "AskUserQuestion": {
            "category": CapabilityCategory.COMMUNICATION.value,
            "subcategory": "user_query",
            "description": "Ask the user a clarifying question",
            "keywords": ["ask", "question", "clarify", "user", "input"],
        },
    }

    def __init__(
        self,
        project_root: Path | None = None,
        inventory_path: Path | None = None,
    ):
        """
        Initialize the capability inventory.

        Args:
            project_root: Path to project root
            inventory_path: Path to capability_inventory.json
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.claude_loop_dir = self.project_root / ".claude-loop"
        self.inventory_path = inventory_path or self.claude_loop_dir / "capability_inventory.json"

        # Ensure .claude-loop directory exists
        self.claude_loop_dir.mkdir(parents=True, exist_ok=True)

        # Load existing inventory
        self._inventory: dict[str, Capability] = self._load_inventory()

    def _load_inventory(self) -> dict[str, Capability]:
        """Load the capability inventory from file."""
        if not self.inventory_path.exists():
            return {}

        try:
            with open(self.inventory_path) as f:
                data = json.load(f)
                return {
                    cap_id: Capability.from_dict(cap_data)
                    for cap_id, cap_data in data.get("capabilities", {}).items()
                }
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_inventory(self) -> None:
        """Save the capability inventory to file."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "capabilities": {
                cap_id: cap.to_dict()
                for cap_id, cap in self._inventory.items()
            },
        }

        try:
            with open(self.inventory_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save inventory: {e}", file=sys.stderr)

    def _generate_capability_id(self, source: str, name: str) -> str:
        """Generate a unique capability ID."""
        content = f"{source}:{name}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"CAP-{hash_val.upper()}"

    def discover_builtin_tools(self) -> list[Capability]:
        """Discover built-in Claude Code tools."""
        capabilities = []
        now = datetime.now().isoformat()

        for tool_name, tool_info in self.BUILTIN_TOOLS.items():
            cap_id = self._generate_capability_id("builtin", tool_name)

            cap = Capability(
                capability_id=cap_id,
                name=tool_name,
                category=tool_info["category"],
                subcategory=tool_info["subcategory"],
                description=tool_info["description"],
                status=CapabilityStatus.AVAILABLE.value,
                source="builtin",
                source_name="Claude Code",
                dependencies=[],
                keywords=tool_info["keywords"],
                version="1.0",
                last_checked=now,
            )

            capabilities.append(cap)
            self._inventory[cap_id] = cap

        return capabilities

    def discover_agents(self) -> list[Capability]:
        """Discover capabilities from agents directory."""
        capabilities = []
        agents_dir = self.project_root / "agents"
        now = datetime.now().isoformat()

        if not agents_dir.exists():
            return capabilities

        # Discover .md agent files
        for agent_file in agents_dir.glob("*.md"):
            agent_name = agent_file.stem

            # Parse agent metadata from frontmatter
            content = agent_file.read_text()
            frontmatter = self._parse_frontmatter(content)

            if not frontmatter:
                continue

            # Extract tools from agent
            tools = frontmatter.get("tools", "").split(", ")

            # Determine category based on agent name
            category = self._infer_category_from_name(agent_name)
            subcategory = self._infer_subcategory_from_name(agent_name, category)

            cap_id = self._generate_capability_id("agent", agent_name)

            cap = Capability(
                capability_id=cap_id,
                name=agent_name,
                category=category,
                subcategory=subcategory,
                description=frontmatter.get("description", ""),
                status=CapabilityStatus.AVAILABLE.value,
                source="agent",
                source_name=agent_name,
                dependencies=tools,
                keywords=self._extract_keywords_from_name(agent_name),
                version="1.0",
                last_checked=now,
            )

            capabilities.append(cap)
            self._inventory[cap_id] = cap

        return capabilities

    def discover_mcp_servers(self) -> list[Capability]:
        """Discover capabilities from MCP servers in config."""
        capabilities = []
        config_path = self.project_root / "config.yaml"
        now = datetime.now().isoformat()

        if not config_path.exists():
            return capabilities

        # Try to parse YAML config
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except (ImportError, Exception):
            # YAML not available or parse error
            return capabilities

        mcp_config = config.get("mcp", {})
        if not mcp_config.get("enabled", False):
            return capabilities

        # Add MCP server as a capability source
        cap_id = self._generate_capability_id("mcp", "mcp_server")

        cap = Capability(
            capability_id=cap_id,
            name="MCP Server Integration",
            category=CapabilityCategory.COMMUNICATION.value,
            subcategory="notification",
            description="Model Context Protocol server for extended capabilities",
            status=CapabilityStatus.LIMITED.value,  # Requires external setup
            source="mcp_server",
            source_name="MCP",
            dependencies=["python3"],
            keywords=["mcp", "server", "integration", "protocol"],
            version="1.0",
            last_checked=now,
            limitations="Requires MCP server to be running",
        )

        capabilities.append(cap)
        self._inventory[cap_id] = cap

        return capabilities

    def discover_skills(self) -> list[Capability]:
        """Discover capabilities from skills directory."""
        capabilities = []
        skills_dir = self.project_root / "skills"
        now = datetime.now().isoformat()

        if not skills_dir.exists():
            return capabilities

        # Walk through skills subdirectories
        for skill_category in skills_dir.iterdir():
            if not skill_category.is_dir():
                continue

            category_name = skill_category.name

            for skill_file in skill_category.glob("*.md"):
                skill_name = skill_file.stem

                cap_id = self._generate_capability_id("skill", f"{category_name}/{skill_name}")

                # Infer category from directory structure
                category = self._infer_category_from_name(category_name)

                cap = Capability(
                    capability_id=cap_id,
                    name=skill_name,
                    category=category,
                    subcategory=category_name,
                    description=f"Skill: {skill_name} from {category_name}",
                    status=CapabilityStatus.AVAILABLE.value,
                    source="skill",
                    source_name=f"{category_name}/{skill_name}",
                    dependencies=[],
                    keywords=self._extract_keywords_from_name(skill_name),
                    version="1.0",
                    last_checked=now,
                )

                capabilities.append(cap)
                self._inventory[cap_id] = cap

        return capabilities

    def discover_lib_tools(self) -> list[Capability]:
        """Discover capabilities from lib/ directory scripts."""
        capabilities = []
        lib_dir = self.project_root / "lib"
        now = datetime.now().isoformat()

        if not lib_dir.exists():
            return capabilities

        # Discover Python and shell scripts
        for script_file in lib_dir.glob("*.py"):
            script_name = script_file.stem

            # Parse docstring for description
            content = script_file.read_text()
            description = self._extract_docstring(content)

            # Infer category from script name
            category = self._infer_category_from_name(script_name)
            subcategory = self._infer_subcategory_from_name(script_name, category)

            cap_id = self._generate_capability_id("lib", script_name)

            cap = Capability(
                capability_id=cap_id,
                name=script_name,
                category=category,
                subcategory=subcategory,
                description=description or f"Library tool: {script_name}",
                status=CapabilityStatus.AVAILABLE.value,
                source="lib",
                source_name=script_file.name,
                dependencies=["python3"],
                keywords=self._extract_keywords_from_name(script_name),
                version="1.0",
                last_checked=now,
            )

            capabilities.append(cap)
            self._inventory[cap_id] = cap

        for script_file in lib_dir.glob("*.sh"):
            script_name = script_file.stem

            cap_id = self._generate_capability_id("lib", script_name)

            cap = Capability(
                capability_id=cap_id,
                name=script_name,
                category=CapabilityCategory.SHELL_EXECUTION.value,
                subcategory="script",
                description=f"Shell script: {script_name}",
                status=CapabilityStatus.AVAILABLE.value,
                source="lib",
                source_name=script_file.name,
                dependencies=["bash"],
                keywords=self._extract_keywords_from_name(script_name),
                version="1.0",
                last_checked=now,
            )

            capabilities.append(cap)
            self._inventory[cap_id] = cap

        return capabilities

    def discover_all(self, save: bool = True) -> list[Capability]:
        """
        Discover all capabilities from all sources.

        Args:
            save: Whether to save inventory after discovery

        Returns:
            List of all discovered capabilities
        """
        all_capabilities = []

        all_capabilities.extend(self.discover_builtin_tools())
        all_capabilities.extend(self.discover_agents())
        all_capabilities.extend(self.discover_mcp_servers())
        all_capabilities.extend(self.discover_skills())
        all_capabilities.extend(self.discover_lib_tools())

        if save:
            self._save_inventory()

        return all_capabilities

    def _parse_frontmatter(self, content: str) -> dict[str, str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}

        try:
            # Find end of frontmatter
            end_idx = content.find("---", 3)
            if end_idx == -1:
                return {}

            frontmatter_text = content[3:end_idx].strip()

            # Simple YAML parsing without external dependency
            result = {}
            for line in frontmatter_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    result[key.strip()] = value.strip()

            return result
        except Exception:
            return {}

    def _extract_docstring(self, content: str) -> str:
        """Extract the module docstring from Python content."""
        match = re.search(r'^"""(.*?)"""', content, re.DOTALL)
        if match:
            docstring = match.group(1).strip()
            # Get first line or first paragraph
            lines = docstring.split("\n\n")[0].split("\n")
            if len(lines) > 1:
                return lines[1].strip()  # Skip module name line
            return lines[0].strip()
        return ""

    def _infer_category_from_name(self, name: str) -> str:
        """Infer capability category from name."""
        name_lower = name.lower().replace("-", "_")

        category_keywords = {
            CapabilityCategory.CODE_GENERATION.value: ["generator", "create", "scaffold"],
            CapabilityCategory.CODE_ANALYSIS.value: ["analyzer", "analysis", "review", "lint", "check"],
            CapabilityCategory.FILE_OPERATIONS.value: ["file", "read", "write", "edit"],
            CapabilityCategory.SHELL_EXECUTION.value: ["shell", "bash", "execute", "run", "worker"],
            CapabilityCategory.UI_AUTOMATION.value: ["ui", "gui", "click", "screenshot", "computer_use"],
            CapabilityCategory.NETWORK_OPERATIONS.value: ["network", "http", "api", "web"],
            CapabilityCategory.DATA_PROCESSING.value: ["parse", "process", "transform", "cluster"],
            CapabilityCategory.TESTING.value: ["test", "validate", "verify"],
            CapabilityCategory.VERSION_CONTROL.value: ["git", "commit", "branch", "merge"],
            CapabilityCategory.DOCUMENTATION.value: ["doc", "readme", "comment"],
            CapabilityCategory.SECURITY.value: ["security", "audit", "scan", "vulnerability"],
            CapabilityCategory.REASONING.value: ["reason", "analyze", "root_cause", "improve", "gap", "pattern"],
            CapabilityCategory.COMMUNICATION.value: ["notify", "report", "log", "monitor"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in name_lower for kw in keywords):
                return category

        return CapabilityCategory.REASONING.value

    def _infer_subcategory_from_name(self, name: str, category: str) -> str:
        """Infer subcategory from name and category."""
        name_lower = name.lower().replace("-", "_")

        subcategories = SUBCATEGORIES.get(category, [])
        for subcat in subcategories:
            if subcat.replace("_", "") in name_lower or name_lower in subcat:
                return subcat

        return subcategories[0] if subcategories else "general"

    def _extract_keywords_from_name(self, name: str) -> list[str]:
        """Extract keywords from capability name."""
        # Split on common delimiters
        parts = re.split(r'[-_\s]', name.lower())
        # Filter out short words
        return [p for p in parts if len(p) > 2]

    def extract_task_requirements(self, task_description: str) -> list[TaskRequirement]:
        """
        Extract capability requirements from a task description.

        Args:
            task_description: Natural language description of the task

        Returns:
            List of TaskRequirement objects
        """
        requirements = []
        task_lower = task_description.lower()

        # Check each category and subcategory for keyword matches
        for category in CapabilityCategory:
            category_value = category.value
            subcategories = SUBCATEGORIES.get(category_value, [])

            for subcategory in subcategories:
                keywords = SKILL_KEYWORDS.get(subcategory, [])
                if not keywords:
                    # Use subcategory name as keyword
                    keywords = [subcategory.replace("_", " ")]

                # Count keyword matches
                matches = sum(1 for kw in keywords if kw in task_lower)
                if matches > 0:
                    confidence = min(1.0, matches * 0.25)
                    requirements.append(TaskRequirement(
                        category=category_value,
                        subcategory=subcategory,
                        keywords=[kw for kw in keywords if kw in task_lower],
                        confidence=confidence,
                    ))

        # Sort by confidence
        requirements.sort(key=lambda r: r.confidence, reverse=True)

        return requirements

    def check_task_capabilities(self, task_description: str) -> CapabilityCheckResult:
        """
        Check if available capabilities can complete a task.

        Args:
            task_description: Natural language description of the task

        Returns:
            CapabilityCheckResult with analysis
        """
        # Extract requirements
        requirements = self.extract_task_requirements(task_description)

        # Find matching capabilities
        available = []
        missing = []
        limited = []

        for req in requirements:
            found = False
            for cap in self._inventory.values():
                if cap.category == req.category and cap.subcategory == req.subcategory:
                    if cap.status == CapabilityStatus.AVAILABLE.value:
                        available.append(cap)
                        found = True
                    elif cap.status == CapabilityStatus.LIMITED.value:
                        limited.append(cap)
                        found = True

            if not found:
                missing.append(req)

        # Calculate overall confidence
        if not requirements:
            confidence = 0.5  # Uncertain
        else:
            matched_count = len(available) + len(limited) * 0.5
            confidence = min(1.0, matched_count / len(requirements))

        # Determine if task can be completed
        critical_missing = [m for m in missing if m.confidence > 0.5]
        can_complete = len(critical_missing) == 0

        # Generate suggestions
        suggestions = []
        for m in missing:
            suggestions.append(
                f"Consider adding capability for {m.category}/{m.subcategory} "
                f"(keywords: {', '.join(m.keywords[:3])})"
            )
        for l in limited:
            suggestions.append(
                f"Capability '{l.name}' has limitations: {l.limitations or 'unspecified'}"
            )

        return CapabilityCheckResult(
            task_description=task_description,
            requirements=requirements,
            available_capabilities=available,
            missing_capabilities=missing,
            limited_capabilities=limited,
            confidence=confidence,
            can_complete=can_complete,
            suggestions=suggestions,
        )

    def get_all_capabilities(self) -> list[Capability]:
        """Get all capabilities in the inventory."""
        return list(self._inventory.values())

    def get_capability_by_id(self, capability_id: str) -> Capability | None:
        """Get a capability by ID."""
        return self._inventory.get(capability_id)

    def get_capabilities_by_category(self, category: str) -> list[Capability]:
        """Get all capabilities in a category."""
        return [c for c in self._inventory.values() if c.category == category]

    def get_capabilities_by_status(self, status: str) -> list[Capability]:
        """Get all capabilities with a specific status."""
        return [c for c in self._inventory.values() if c.status == status]

    def update_capability_status(
        self,
        capability_id: str,
        status: str,
        limitations: str = "",
    ) -> bool:
        """Update the status of a capability."""
        cap = self._inventory.get(capability_id)
        if not cap:
            return False

        cap.status = status
        cap.limitations = limitations
        cap.last_checked = datetime.now().isoformat()

        self._save_inventory()
        return True

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of the inventory."""
        capabilities = list(self._inventory.values())

        by_status = {}
        for status in CapabilityStatus:
            by_status[status.value] = len([c for c in capabilities if c.status == status.value])

        by_category = {}
        for category in CapabilityCategory:
            by_category[category.value] = len([c for c in capabilities if c.category == category.value])

        by_source = {}
        for cap in capabilities:
            by_source[cap.source] = by_source.get(cap.source, 0) + 1

        return {
            "total_capabilities": len(capabilities),
            "by_status": by_status,
            "by_category": by_category,
            "by_source": by_source,
            "last_updated": max(
                (c.last_checked for c in capabilities if c.last_checked),
                default="never",
            ),
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Capability Inventory Tracker for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/capability-inventory.py list
    python lib/capability-inventory.py list --category code_analysis
    python lib/capability-inventory.py check "Write Python tests for the API"
    python lib/capability-inventory.py discover
    python lib/capability-inventory.py show CAP-12345678
    python lib/capability-inventory.py status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List all capabilities"
    )
    list_parser.add_argument(
        "--category",
        type=str,
        help="Filter by category",
    )
    list_parser.add_argument(
        "--status",
        choices=["available", "limited", "unavailable", "unknown"],
        help="Filter by status",
    )
    list_parser.add_argument(
        "--source",
        type=str,
        help="Filter by source (builtin, agent, mcp_server, skill, lib)",
    )
    list_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check capabilities for a task"
    )
    check_parser.add_argument(
        "task_description",
        type=str,
        help="Description of the task to check",
    )
    check_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # discover command
    discover_parser = subparsers.add_parser(
        "discover", help="Discover and update capabilities"
    )
    discover_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # show command
    show_parser = subparsers.add_parser(
        "show", help="Show details of a capability"
    )
    show_parser.add_argument(
        "capability_id",
        type=str,
        help="Capability ID to show",
    )
    show_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # status command
    status_parser = subparsers.add_parser(
        "status", help="Show inventory summary status"
    )
    status_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # categories command
    categories_parser = subparsers.add_parser(
        "categories", help="List all capability categories"
    )
    categories_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # update-status command
    update_parser = subparsers.add_parser(
        "update-status", help="Update capability status"
    )
    update_parser.add_argument(
        "capability_id",
        type=str,
        help="Capability ID to update",
    )
    update_parser.add_argument(
        "status",
        choices=["available", "limited", "unavailable"],
        help="New status",
    )
    update_parser.add_argument(
        "--limitations",
        type=str,
        default="",
        help="Limitations description (for limited status)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize inventory
    project_root = Path(__file__).parent.parent
    inventory = CapabilityInventory(project_root=project_root)

    if args.command == "list":
        capabilities = inventory.get_all_capabilities()

        # Apply filters
        if args.category:
            capabilities = [c for c in capabilities if c.category == args.category]
        if args.status:
            capabilities = [c for c in capabilities if c.status == args.status]
        if args.source:
            capabilities = [c for c in capabilities if c.source == args.source]

        if args.json:
            print(json.dumps([c.to_dict() for c in capabilities], indent=2))
        else:
            if not capabilities:
                print("No capabilities found. Run 'discover' to populate inventory.")
                return

            print(f"{'ID':<15} {'Name':<25} {'Category':<20} {'Status':<12} Source")
            print("-" * 85)
            for cap in sorted(capabilities, key=lambda c: (c.category, c.name)):
                print(f"{cap.capability_id:<15} {cap.name[:24]:<25} {cap.category:<20} {cap.status:<12} {cap.source}")

    elif args.command == "check":
        result = inventory.check_task_capabilities(args.task_description)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"=== Task Capability Check ===\n")
            print(f"Task: {result.task_description[:80]}...")
            print(f"Can Complete: {'Yes' if result.can_complete else 'No'}")
            print(f"Confidence: {result.confidence:.0%}")
            print()

            if result.requirements:
                print("Required Capabilities:")
                for req in result.requirements[:5]:
                    print(f"  - {req.category}/{req.subcategory} ({req.confidence:.0%})")
                    if req.keywords:
                        print(f"    Keywords: {', '.join(req.keywords[:3])}")
            else:
                print("No specific requirements detected.")

            print()

            if result.available_capabilities:
                print(f"Available ({len(result.available_capabilities)}):")
                for cap in result.available_capabilities[:5]:
                    print(f"  + {cap.name} ({cap.category})")

            if result.limited_capabilities:
                print(f"\nLimited ({len(result.limited_capabilities)}):")
                for cap in result.limited_capabilities:
                    print(f"  ~ {cap.name} - {cap.limitations or 'unspecified limitations'}")

            if result.missing_capabilities:
                print(f"\nMissing ({len(result.missing_capabilities)}):")
                for req in result.missing_capabilities:
                    print(f"  - {req.category}/{req.subcategory}")

            if result.suggestions:
                print("\nSuggestions:")
                for suggestion in result.suggestions[:3]:
                    print(f"  * {suggestion}")

    elif args.command == "discover":
        capabilities = inventory.discover_all(save=True)

        if args.json:
            print(json.dumps([c.to_dict() for c in capabilities], indent=2))
        else:
            print(f"=== Capability Discovery ===\n")
            print(f"Discovered {len(capabilities)} capabilities:\n")

            by_source = {}
            for cap in capabilities:
                by_source[cap.source] = by_source.get(cap.source, 0) + 1

            for source, count in sorted(by_source.items()):
                print(f"  {source}: {count}")

            print(f"\nInventory saved to: {inventory.inventory_path}")

    elif args.command == "show":
        cap = inventory.get_capability_by_id(args.capability_id)

        if not cap:
            print(f"Error: Capability '{args.capability_id}' not found")
            print("\nUse 'list' to see available capabilities")
            sys.exit(1)

        if args.json:
            print(json.dumps(cap.to_dict(), indent=2))
        else:
            print(f"=== Capability: {cap.capability_id} ===\n")
            print(f"Name: {cap.name}")
            print(f"Category: {cap.category}")
            print(f"Subcategory: {cap.subcategory}")
            print(f"Status: {cap.status}")
            print(f"Source: {cap.source} ({cap.source_name})")
            print()
            print(f"Description:")
            print(f"  {cap.description}")
            print()
            if cap.dependencies:
                print(f"Dependencies: {', '.join(cap.dependencies)}")
            if cap.keywords:
                print(f"Keywords: {', '.join(cap.keywords)}")
            if cap.limitations:
                print(f"Limitations: {cap.limitations}")
            print()
            print(f"Version: {cap.version}")
            print(f"Last Checked: {cap.last_checked[:19] if cap.last_checked else 'N/A'}")

    elif args.command == "status":
        summary = inventory.get_summary()

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=== Capability Inventory Status ===\n")
            print(f"Total Capabilities: {summary['total_capabilities']}")
            print(f"Last Updated: {summary['last_updated'][:19] if summary['last_updated'] != 'never' else 'never'}")
            print()
            print("By Status:")
            for status, count in summary.get('by_status', {}).items():
                if count > 0:
                    print(f"  {status}: {count}")
            print()
            print("By Category:")
            for category, count in sorted(summary.get('by_category', {}).items()):
                if count > 0:
                    print(f"  {category}: {count}")
            print()
            print("By Source:")
            for source, count in summary.get('by_source', {}).items():
                print(f"  {source}: {count}")

    elif args.command == "categories":
        if args.json:
            output = {
                cat.value: {
                    "subcategories": SUBCATEGORIES.get(cat.value, []),
                }
                for cat in CapabilityCategory
            }
            print(json.dumps(output, indent=2))
        else:
            print("=== Capability Categories ===\n")
            for cat in CapabilityCategory:
                subcats = SUBCATEGORIES.get(cat.value, [])
                print(f"{cat.value}")
                if subcats:
                    print(f"  Subcategories: {', '.join(subcats[:5])}")
                    if len(subcats) > 5:
                        print(f"                 ... and {len(subcats) - 5} more")
                print()

    elif args.command == "update-status":
        success = inventory.update_capability_status(
            args.capability_id,
            args.status,
            args.limitations,
        )

        if success:
            print(f"Updated {args.capability_id} to status: {args.status}")
        else:
            print(f"Error: Capability '{args.capability_id}' not found")
            sys.exit(1)


if __name__ == "__main__":
    main()
