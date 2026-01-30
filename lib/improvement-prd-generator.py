#!/usr/bin/env python3
"""
improvement-prd-generator.py - Improvement PRD Generator for claude-loop

Automatically generates PRDs from capability gaps identified by the self-improvement
pipeline. Creates generalizable user stories with acceptance criteria, test cases,
and appropriate dependencies.

Features:
- Generates 5-15 user stories per capability gap
- Stories are generalizable (not specific to one use case)
- Includes test cases in acceptance criteria
- Sets story dependencies based on logical order
- Assigns complexity and suggested model per story
- Saves PRDs to .claude-loop/improvements/ with pending_review status

Usage:
    python lib/improvement-prd-generator.py generate <gap_id>
    python lib/improvement-prd-generator.py generate <gap_id> --json
    python lib/improvement-prd-generator.py list
    python lib/improvement-prd-generator.py show <prd_name>
    python lib/improvement-prd-generator.py pending
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Import from sibling modules with hyphenated names
import importlib.util


def _import_module(module_name: str, file_name: str):
    """Import a module from a hyphenated filename."""
    module_path = Path(__file__).parent / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {module_name} from {file_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_gap_generalizer = _import_module("gap_generalizer", "gap-generalizer.py")
GeneralizedGap = _gap_generalizer.GeneralizedGap
GapGeneralizer = _gap_generalizer.GapGeneralizer
CapabilityCategory = _gap_generalizer.CapabilityCategory
TASK_FAMILIES = _gap_generalizer.TASK_FAMILIES
FEASIBILITY_SCORES = _gap_generalizer.FEASIBILITY_SCORES


# ============================================================================
# Story Templates by Category
# ============================================================================

# Each category has a template of common stories for addressing gaps
# Stories are designed to be generalizable across different use cases

STORY_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    CapabilityCategory.UI_INTERACTION: [
        {
            "title": "Element Detection Framework",
            "description": "Create a framework for detecting UI elements across different platforms",
            "criteria": [
                "Create lib/ui-element-detector module",
                "Support detection by: id, class, text, position",
                "Handle dynamic element loading (wait strategies)",
                "Return structured element info: bounds, text, type, state",
                "Add test: detect button element in sample app",
                "Add test: handle element not found gracefully",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Screenshot Analysis Utility",
            "description": "Implement screenshot capture and analysis for visual verification",
            "criteria": [
                "Create lib/screenshot-analyzer module",
                "Capture full screen or specific window",
                "Detect regions of interest (ROI) in screenshots",
                "Compare screenshots for visual changes",
                "Add test: capture and compare screenshots",
                "Add test: detect specific region in screenshot",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Interaction Abstraction Layer",
            "description": "Create platform-agnostic UI interaction commands",
            "criteria": [
                "Create lib/ui-interaction module",
                "Abstract click, type, scroll, select operations",
                "Support coordinate-based and element-based interactions",
                "Handle interaction failures with retry logic",
                "Add test: perform click on element",
                "Add test: type text into input field",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Window Management Utilities",
            "description": "Implement window detection and manipulation capabilities",
            "criteria": [
                "Create lib/window-manager module",
                "List available windows and their properties",
                "Focus, minimize, maximize, close windows",
                "Detect window state changes",
                "Add test: list and focus on specific window",
                "Add test: detect window creation",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "UI State Verification",
            "description": "Create utilities for verifying UI state after interactions",
            "criteria": [
                "Create lib/ui-state-verifier module",
                "Verify element visibility, enabled state, text content",
                "Wait for state transitions with configurable timeout",
                "Support assertion chaining for complex verifications",
                "Add test: verify button becomes enabled after input",
                "Add test: wait for loading indicator to disappear",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.FILE_HANDLING: [
        {
            "title": "Robust File Operations",
            "description": "Create safe file operations with proper error handling",
            "criteria": [
                "Create lib/safe-file-ops module",
                "Implement atomic write with temporary files",
                "Handle permission errors gracefully",
                "Support dry-run mode for destructive operations",
                "Add test: atomic write survives interruption",
                "Add test: permission error is reported clearly",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "File Path Resolution",
            "description": "Implement intelligent path resolution and validation",
            "criteria": [
                "Create lib/path-resolver module",
                "Resolve relative, absolute, and glob paths",
                "Validate path existence and accessibility",
                "Handle symlinks and special paths",
                "Add test: resolve glob pattern to files",
                "Add test: detect and handle broken symlinks",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Directory Tree Operations",
            "description": "Implement directory traversal and manipulation",
            "criteria": [
                "Create lib/directory-ops module",
                "Recursive listing with filters",
                "Safe recursive delete with confirmation",
                "Copy/move directory trees",
                "Add test: list directory with depth limit",
                "Add test: copy directory preserving structure",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "File Watching Service",
            "description": "Monitor files and directories for changes",
            "criteria": [
                "Create lib/file-watcher module",
                "Watch for create, modify, delete events",
                "Support glob patterns for watched paths",
                "Debounce rapid successive changes",
                "Add test: detect file creation",
                "Add test: debounce rapid file changes",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Temporary File Management",
            "description": "Safe creation and cleanup of temporary files",
            "criteria": [
                "Create lib/temp-file-manager module",
                "Create temp files with automatic cleanup",
                "Support temp directory isolation per task",
                "Track all temp files for cleanup on failure",
                "Add test: temp file is cleaned up on exit",
                "Add test: temp directory isolates tasks",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
    ],
    CapabilityCategory.NETWORK: [
        {
            "title": "HTTP Client with Retry",
            "description": "Create robust HTTP client with automatic retry",
            "criteria": [
                "Create lib/http-client module",
                "Automatic retry with exponential backoff",
                "Handle common HTTP errors (429, 500, 503)",
                "Support request/response logging",
                "Add test: retry on 429 with backoff",
                "Add test: timeout handling",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Network Error Classification",
            "description": "Classify network errors for appropriate handling",
            "criteria": [
                "Create lib/network-error-classifier module",
                "Distinguish retryable vs non-retryable errors",
                "Detect DNS, connection, timeout, SSL errors",
                "Suggest recovery action for each error type",
                "Add test: classify timeout as retryable",
                "Add test: classify 404 as non-retryable",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Connection Health Monitor",
            "description": "Monitor and report network connectivity status",
            "criteria": [
                "Create lib/connection-monitor module",
                "Check connectivity to specific hosts",
                "Detect network interface changes",
                "Report latency and packet loss",
                "Add test: detect connectivity loss",
                "Add test: measure latency to host",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Download Manager",
            "description": "Reliable file download with progress and resume",
            "criteria": [
                "Create lib/download-manager module",
                "Support resume of partial downloads",
                "Report download progress",
                "Verify downloaded file integrity (checksum)",
                "Add test: resume interrupted download",
                "Add test: verify checksum after download",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Network Request Caching",
            "description": "Cache network responses to reduce redundant requests",
            "criteria": [
                "Create lib/request-cache module",
                "Cache responses with TTL",
                "Support cache invalidation",
                "Respect HTTP cache headers",
                "Add test: cache hit returns cached response",
                "Add test: expired cache is refreshed",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.PARSING: [
        {
            "title": "Format Detection",
            "description": "Automatically detect data format from content",
            "criteria": [
                "Create lib/format-detector module",
                "Detect JSON, YAML, XML, CSV, INI formats",
                "Handle malformed content gracefully",
                "Return confidence score with detection",
                "Add test: detect JSON from content",
                "Add test: handle mixed format files",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Flexible Parser Framework",
            "description": "Create a unified parser interface for multiple formats",
            "criteria": [
                "Create lib/flexible-parser module",
                "Unified parse() function for all formats",
                "Convert between formats (JSON to YAML, etc.)",
                "Preserve comments where possible",
                "Add test: parse and convert JSON to YAML",
                "Add test: round-trip preserves data",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Schema Validation",
            "description": "Validate parsed data against schemas",
            "criteria": [
                "Create lib/schema-validator module",
                "Support JSON Schema validation",
                "Return detailed validation errors",
                "Suggest fixes for common validation errors",
                "Add test: validate against JSON schema",
                "Add test: report missing required fields",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Error Recovery Parser",
            "description": "Parse malformed data with best-effort recovery",
            "criteria": [
                "Create lib/recovery-parser module",
                "Attempt to parse despite syntax errors",
                "Return partial results with error locations",
                "Suggest corrections for common syntax issues",
                "Add test: parse JSON with trailing comma",
                "Add test: recover partial data from broken file",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Streaming Parser",
            "description": "Parse large files without loading entirely into memory",
            "criteria": [
                "Create lib/streaming-parser module",
                "Stream parse JSON/XML line by line",
                "Support early termination on match",
                "Report progress during parsing",
                "Add test: parse large JSON file streaming",
                "Add test: find match without reading whole file",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.TOOL_INTEGRATION: [
        {
            "title": "Tool Discovery",
            "description": "Discover and catalog available tools and their capabilities",
            "criteria": [
                "Create lib/tool-discovery module",
                "Detect installed CLI tools and versions",
                "Query MCP servers for available tools",
                "Build capability index from tool metadata",
                "Add test: discover git and report version",
                "Add test: list MCP tools from server",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Tool Invocation Wrapper",
            "description": "Safe wrapper for external tool invocation",
            "criteria": [
                "Create lib/tool-wrapper module",
                "Sanitize inputs to prevent injection",
                "Capture stdout/stderr/exit code",
                "Support timeouts and resource limits",
                "Add test: capture tool output",
                "Add test: timeout kills hanging tool",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Tool Output Parser",
            "description": "Parse common tool output formats",
            "criteria": [
                "Create lib/tool-output-parser module",
                "Parse table, list, and structured outputs",
                "Handle colored/formatted terminal output",
                "Extract key-value pairs from output",
                "Add test: parse git status output",
                "Add test: strip ANSI codes from output",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Tool Chain Orchestrator",
            "description": "Orchestrate multiple tools in sequence with data flow",
            "criteria": [
                "Create lib/tool-chain module",
                "Define tool chains with data dependencies",
                "Handle intermediate failures gracefully",
                "Support parallel tool execution where safe",
                "Add test: run tool chain with data flow",
                "Add test: handle mid-chain failure",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Tool Fallback Registry",
            "description": "Register fallback tools for unavailable primary tools",
            "criteria": [
                "Create lib/tool-fallback module",
                "Register primary and fallback tools",
                "Automatic fallback when primary fails",
                "Report when fallback is used",
                "Add test: fallback to alternative tool",
                "Add test: report fallback usage",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
    ],
    CapabilityCategory.STATE_MANAGEMENT: [
        {
            "title": "Session State Store",
            "description": "Persist and restore session state across operations",
            "criteria": [
                "Create lib/session-state module",
                "Store session data with unique session ID",
                "Automatic save on state change",
                "Restore session from previous run",
                "Add test: save and restore session state",
                "Add test: concurrent session isolation",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Checkpoint System",
            "description": "Create checkpoints for long-running operations",
            "criteria": [
                "Create lib/checkpoint module",
                "Create named checkpoints during execution",
                "Restore from checkpoint on failure",
                "Clean up old checkpoints automatically",
                "Add test: restore from checkpoint after failure",
                "Add test: checkpoint cleanup by age",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "State Diff and Merge",
            "description": "Track state changes and handle conflicting updates",
            "criteria": [
                "Create lib/state-diff module",
                "Compute diff between state snapshots",
                "Merge non-conflicting state changes",
                "Report conflicts for manual resolution",
                "Add test: merge non-conflicting changes",
                "Add test: detect and report conflicts",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Context Propagation",
            "description": "Propagate context across nested operations",
            "criteria": [
                "Create lib/context-propagator module",
                "Pass context through call stack",
                "Support context inheritance and override",
                "Clean up context on operation completion",
                "Add test: nested context inheritance",
                "Add test: context override in child",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Transaction Manager",
            "description": "Manage atomic multi-step transactions",
            "criteria": [
                "Create lib/transaction-manager module",
                "Begin, commit, rollback transactions",
                "Support nested transactions",
                "Automatic rollback on unhandled error",
                "Add test: rollback on error",
                "Add test: nested transaction isolation",
            ],
            "complexity": "complex",
            "model": "opus",
        },
    ],
    CapabilityCategory.PERMISSION_HANDLING: [
        {
            "title": "Permission Checker",
            "description": "Check permissions before attempting operations",
            "criteria": [
                "Create lib/permission-checker module",
                "Check file read/write/execute permissions",
                "Verify directory traversal permissions",
                "Report specific permission missing",
                "Add test: check file write permission",
                "Add test: report permission denied reason",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Privilege Elevation Handler",
            "description": "Handle operations requiring elevated privileges",
            "criteria": [
                "Create lib/privilege-handler module",
                "Detect when elevation is needed",
                "Request elevation through appropriate mechanism",
                "Report operations that cannot be elevated",
                "Add test: detect need for elevation",
                "Add test: handle elevation denied",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Credential Manager",
            "description": "Securely handle credentials for authenticated operations",
            "criteria": [
                "Create lib/credential-manager module",
                "Store credentials securely (keychain/vault)",
                "Retrieve credentials by service name",
                "Handle credential expiration",
                "Add test: store and retrieve credential",
                "Add test: handle expired credential",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Sandbox Escape Detector",
            "description": "Detect and prevent sandbox escape attempts",
            "criteria": [
                "Create lib/sandbox-monitor module",
                "Detect file access outside allowed paths",
                "Monitor process spawn attempts",
                "Log and block unauthorized operations",
                "Add test: block access outside sandbox",
                "Add test: log unauthorized attempt",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Permission Request UI",
            "description": "User interface for requesting permissions",
            "criteria": [
                "Create lib/permission-request module",
                "Present clear permission request to user",
                "Remember user permission decisions",
                "Support 'always allow' and 'deny once'",
                "Add test: present permission dialog",
                "Add test: remember user decision",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.API_INTERACTION: [
        {
            "title": "API Client Generator",
            "description": "Generate API clients from OpenAPI/Swagger specs",
            "criteria": [
                "Create lib/api-client-generator module",
                "Parse OpenAPI 3.0 specifications",
                "Generate typed client methods",
                "Include authentication handling",
                "Add test: generate client from spec",
                "Add test: generated client makes valid requests",
            ],
            "complexity": "complex",
            "model": "opus",
        },
        {
            "title": "Rate Limiter",
            "description": "Implement client-side rate limiting for API calls",
            "criteria": [
                "Create lib/rate-limiter module",
                "Track request counts per time window",
                "Queue requests exceeding limit",
                "Support multiple rate limit strategies",
                "Add test: enforce rate limit",
                "Add test: queue and retry rate limited requests",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "API Response Cache",
            "description": "Cache API responses with intelligent invalidation",
            "criteria": [
                "Create lib/api-cache module",
                "Cache GET responses by URL and params",
                "Invalidate cache on write operations",
                "Support manual cache clear",
                "Add test: cache GET response",
                "Add test: invalidate on POST",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Webhook Handler",
            "description": "Receive and process webhook notifications",
            "criteria": [
                "Create lib/webhook-handler module",
                "Start lightweight HTTP server for webhooks",
                "Verify webhook signatures",
                "Route webhooks to registered handlers",
                "Add test: receive and verify webhook",
                "Add test: route to correct handler",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "API Error Translator",
            "description": "Translate API errors to actionable messages",
            "criteria": [
                "Create lib/api-error-translator module",
                "Map common HTTP errors to user-friendly messages",
                "Extract error details from response body",
                "Suggest fix actions for common errors",
                "Add test: translate 401 to auth error",
                "Add test: extract API error message",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
    ],
    CapabilityCategory.ERROR_RECOVERY: [
        {
            "title": "Retry Strategy Framework",
            "description": "Configurable retry strategies for failed operations",
            "criteria": [
                "Create lib/retry-strategy module",
                "Support exponential backoff, linear, constant",
                "Configurable max retries and delays",
                "Support conditional retry based on error type",
                "Add test: exponential backoff timing",
                "Add test: skip retry for non-retryable errors",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Circuit Breaker",
            "description": "Implement circuit breaker pattern for failing services",
            "criteria": [
                "Create lib/circuit-breaker module",
                "Track failure rate over time window",
                "Open circuit when threshold exceeded",
                "Half-open state for recovery testing",
                "Add test: circuit opens on failures",
                "Add test: circuit recovers after cooldown",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Fallback Chain",
            "description": "Define fallback chains for graceful degradation",
            "criteria": [
                "Create lib/fallback-chain module",
                "Define primary and fallback operations",
                "Execute fallbacks in order until success",
                "Report which fallback was used",
                "Add test: fallback to secondary on failure",
                "Add test: exhaust all fallbacks and fail",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Error Aggregator",
            "description": "Aggregate and deduplicate errors for reporting",
            "criteria": [
                "Create lib/error-aggregator module",
                "Group similar errors by type and message",
                "Track error frequency over time",
                "Generate error summary report",
                "Add test: aggregate similar errors",
                "Add test: track frequency correctly",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Recovery Action Registry",
            "description": "Register and execute recovery actions for specific errors",
            "criteria": [
                "Create lib/recovery-actions module",
                "Register recovery handlers by error type",
                "Execute recovery and retry original operation",
                "Support async recovery actions",
                "Add test: execute recovery and retry",
                "Add test: handle recovery failure",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.VALIDATION: [
        {
            "title": "Input Validator Framework",
            "description": "Validate inputs with composable validators",
            "criteria": [
                "Create lib/input-validator module",
                "Support type, range, pattern validators",
                "Compose validators with AND/OR logic",
                "Return detailed validation errors",
                "Add test: validate string with pattern",
                "Add test: compose multiple validators",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Data Sanitizer",
            "description": "Sanitize user input to prevent injection attacks",
            "criteria": [
                "Create lib/data-sanitizer module",
                "Escape HTML, SQL, shell special characters",
                "Support allow-list sanitization",
                "Preserve safe content while removing dangerous",
                "Add test: escape HTML entities",
                "Add test: remove shell metacharacters",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Assertion Library",
            "description": "Rich assertion library for runtime checks",
            "criteria": [
                "Create lib/assertions module",
                "Support common assertions (equals, contains, matches)",
                "Provide detailed failure messages",
                "Support soft assertions (collect all failures)",
                "Add test: assertion with detailed message",
                "Add test: soft assertion collects multiple",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
        {
            "title": "Contract Validator",
            "description": "Validate function pre/post conditions and invariants",
            "criteria": [
                "Create lib/contract-validator module",
                "Define preconditions and postconditions",
                "Support class invariants",
                "Configurable enforcement (on/off/log)",
                "Add test: enforce precondition",
                "Add test: check postcondition after call",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Data Quality Checker",
            "description": "Check data quality metrics and completeness",
            "criteria": [
                "Create lib/data-quality module",
                "Check for null, empty, duplicate values",
                "Validate data type consistency",
                "Generate data quality report",
                "Add test: detect null values",
                "Add test: report type inconsistencies",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
    ],
    CapabilityCategory.UNKNOWN: [
        {
            "title": "Capability Investigation",
            "description": "Investigate the unknown capability gap to categorize it",
            "criteria": [
                "Analyze failed operations for common patterns",
                "Document the capability requirement",
                "Propose categorization based on analysis",
                "Add test: verify categorization logic",
            ],
            "complexity": "medium",
            "model": "sonnet",
        },
        {
            "title": "Generic Error Handler",
            "description": "Create generic error handling for uncategorized failures",
            "criteria": [
                "Create lib/generic-error-handler module",
                "Log detailed error information",
                "Suggest potential categories for the error",
                "Add test: log and categorize unknown error",
            ],
            "complexity": "simple",
            "model": "haiku",
        },
    ],
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class UserStory:
    """A user story within a PRD."""

    id: str
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    dependencies: list[str] = field(default_factory=list)
    fileScope: list[str] = field(default_factory=list)
    estimatedComplexity: str = "medium"  # simple, medium, complex
    suggestedModel: str = "sonnet"  # haiku, sonnet, opus
    passes: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptanceCriteria": self.acceptanceCriteria,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "fileScope": self.fileScope,
            "estimatedComplexity": self.estimatedComplexity,
            "suggestedModel": self.suggestedModel,
            "passes": self.passes,
            "notes": self.notes,
        }


@dataclass
class ImprovementPRD:
    """A PRD generated from a capability gap."""

    name: str
    project: str
    branchName: str
    description: str
    gap_id: str
    gap_category: str
    priority_score: float
    userStories: list[UserStory]

    # Status tracking
    status: str = "pending_review"  # pending_review, approved, rejected, in_progress, complete
    created_at: str = ""
    updated_at: str = ""
    reviewed_at: str = ""
    reviewer_notes: str = ""

    # Metadata
    estimated_effort: str = ""
    affected_task_types: list[str] = field(default_factory=list)
    source_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "project": self.project,
            "branchName": self.branchName,
            "description": self.description,
            "gap_id": self.gap_id,
            "gap_category": self.gap_category,
            "priority_score": round(self.priority_score, 2),
            "userStories": [s.to_dict() for s in self.userStories],
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "reviewer_notes": self.reviewer_notes,
            "estimated_effort": self.estimated_effort,
            "affected_task_types": self.affected_task_types,
            "source_patterns": self.source_patterns,
            "parallelization": {
                "enabled": True,
                "maxWorkers": 2,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImprovementPRD:
        stories = [
            UserStory(
                id=s["id"],
                title=s["title"],
                description=s["description"],
                acceptanceCriteria=s["acceptanceCriteria"],
                priority=s["priority"],
                dependencies=s.get("dependencies", []),
                fileScope=s.get("fileScope", []),
                estimatedComplexity=s.get("estimatedComplexity", "medium"),
                suggestedModel=s.get("suggestedModel", "sonnet"),
                passes=s.get("passes", False),
                notes=s.get("notes", ""),
            )
            for s in data.get("userStories", [])
        ]

        return cls(
            name=data.get("name", ""),
            project=data.get("project", ""),
            branchName=data.get("branchName", ""),
            description=data.get("description", ""),
            gap_id=data.get("gap_id", ""),
            gap_category=data.get("gap_category", ""),
            priority_score=data.get("priority_score", 0.0),
            userStories=stories,
            status=data.get("status", "pending_review"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            reviewed_at=data.get("reviewed_at", ""),
            reviewer_notes=data.get("reviewer_notes", ""),
            estimated_effort=data.get("estimated_effort", ""),
            affected_task_types=data.get("affected_task_types", []),
            source_patterns=data.get("source_patterns", []),
        )


# ============================================================================
# PRD Generator
# ============================================================================

class ImprovementPRDGenerator:
    """
    Generates improvement PRDs from capability gaps.

    The generation process:
    1. Load gap details from the registry
    2. Select appropriate story templates for the gap category
    3. Customize stories based on gap specifics
    4. Set dependencies based on logical order
    5. Calculate effort estimate
    6. Save PRD to improvements directory
    """

    def __init__(
        self,
        project_root: Path | None = None,
        improvements_dir: Path | None = None,
        use_llm: bool = True,
    ):
        """
        Initialize the generator.

        Args:
            project_root: Path to project root
            improvements_dir: Path to improvements storage directory
            use_llm: Whether to use LLM for story customization
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.claude_loop_dir = self.project_root / ".claude-loop"
        self.improvements_dir = improvements_dir or self.claude_loop_dir / "improvements"
        self.use_llm = use_llm

        # Ensure improvements directory exists
        self.improvements_dir.mkdir(parents=True, exist_ok=True)

        # Initialize gap generalizer for loading gaps
        self.gap_generalizer = GapGeneralizer(project_root=self.project_root)

    def _generate_prd_name(self, gap: GeneralizedGap) -> str:
        """Generate a unique PRD name from the gap."""
        # Create a slug from the category
        category_slug = gap.category.lower().replace("_", "-")

        # Add hash for uniqueness
        hash_val = hashlib.sha256(gap.gap_id.encode()).hexdigest()[:6]

        return f"improve-{category_slug}-{hash_val}"

    def _generate_branch_name(self, prd_name: str) -> str:
        """Generate a git branch name for the PRD."""
        return f"feature/{prd_name}"

    def _select_stories(
        self,
        gap: GeneralizedGap,
        min_stories: int = 5,
        max_stories: int = 15,
    ) -> list[dict[str, Any]]:
        """
        Select story templates appropriate for the gap.

        Args:
            gap: The GeneralizedGap to generate stories for
            min_stories: Minimum number of stories
            max_stories: Maximum number of stories

        Returns:
            List of story template dictionaries
        """
        # Get templates for this category
        templates = STORY_TEMPLATES.get(gap.category, STORY_TEMPLATES[CapabilityCategory.UNKNOWN])

        # If we have enough templates, use them all
        if len(templates) >= min_stories:
            return templates[:max_stories]

        # Otherwise, supplement with generic stories
        stories = list(templates)

        # Add generic stories based on gap description
        if len(stories) < min_stories:
            generic_stories = self._generate_generic_stories(gap, min_stories - len(stories))
            stories.extend(generic_stories)

        return stories[:max_stories]

    def _generate_generic_stories(
        self,
        gap: GeneralizedGap,
        count: int,
    ) -> list[dict[str, Any]]:
        """Generate generic stories based on gap description."""
        generic = []

        # Documentation story
        if count > 0:
            generic.append({
                "title": f"Document {gap.category.replace('_', ' ').title()} Patterns",
                "description": f"Document common patterns and best practices for {gap.category.lower().replace('_', ' ')}",
                "criteria": [
                    "Create documentation in docs/ directory",
                    "Include code examples for common patterns",
                    "Document error handling approaches",
                    "Add troubleshooting guide",
                ],
                "complexity": "simple",
                "model": "haiku",
            })

        # Integration test story
        if count > 1:
            generic.append({
                "title": f"Integration Tests for {gap.category.replace('_', ' ').title()}",
                "description": f"Create comprehensive integration tests for {gap.category.lower().replace('_', ' ')} capabilities",
                "criteria": [
                    "Create tests/integration/ test file",
                    "Cover happy path scenarios",
                    "Cover error handling scenarios",
                    "Add performance benchmarks",
                ],
                "complexity": "medium",
                "model": "sonnet",
            })

        # Monitoring story
        if count > 2:
            generic.append({
                "title": f"Monitoring for {gap.category.replace('_', ' ').title()}",
                "description": f"Add monitoring and metrics for {gap.category.lower().replace('_', ' ')} operations",
                "criteria": [
                    "Track operation success/failure rates",
                    "Log operation durations",
                    "Alert on anomalies",
                    "Add dashboard metrics",
                ],
                "complexity": "medium",
                "model": "sonnet",
            })

        return generic[:count]

    def _customize_story(
        self,
        template: dict[str, Any],
        gap: GeneralizedGap,
        index: int,
    ) -> UserStory:
        """
        Customize a story template for the specific gap.

        Args:
            template: Story template dictionary
            gap: The GeneralizedGap
            index: Story index (for ID and priority)

        Returns:
            Customized UserStory
        """
        # Generate story ID
        story_id = f"IMP-{index:03d}"

        # Determine file scope based on title
        title_slug = re.sub(r'[^a-z0-9]+', '-', template["title"].lower()).strip('-')
        file_scope = [f"lib/{title_slug}.py"]

        # Add test file if criteria mention tests
        if any("test" in c.lower() for c in template.get("criteria", [])):
            file_scope.append(f"tests/test_{title_slug.replace('-', '_')}.py")

        # Map complexity to model
        complexity = template.get("complexity", "medium")
        model = template.get("model", "sonnet")

        # Create description with gap context
        description = f"As a developer, I want {template['description'].lower()} to address the {gap.category.lower().replace('_', ' ')} capability gap"

        return UserStory(
            id=story_id,
            title=template["title"],
            description=description,
            acceptanceCriteria=template.get("criteria", []),
            priority=index,
            dependencies=[],  # Will be set later
            fileScope=file_scope,
            estimatedComplexity=complexity,
            suggestedModel=model,
            passes=False,
            notes="Auto-generated from capability gap analysis",
        )

    def _set_dependencies(self, stories: list[UserStory]) -> None:
        """
        Set dependencies between stories based on logical order.

        Simple heuristic: each story depends on the previous one,
        except for the first story.
        """
        for i, story in enumerate(stories):
            if i > 0:
                # Depend on previous story
                story.dependencies = [stories[i - 1].id]

            # Complex stories might depend on simpler related ones
            if story.estimatedComplexity == "complex":
                # Find simpler stories that might be prerequisites
                for prev_story in stories[:i]:
                    if prev_story.estimatedComplexity == "simple":
                        if prev_story.id not in story.dependencies:
                            story.dependencies.append(prev_story.id)

    def _estimate_effort(self, stories: list[UserStory]) -> str:
        """Estimate total effort for the PRD."""
        # Simple heuristic based on complexity counts
        simple_count = sum(1 for s in stories if s.estimatedComplexity == "simple")
        medium_count = sum(1 for s in stories if s.estimatedComplexity == "medium")
        complex_count = sum(1 for s in stories if s.estimatedComplexity == "complex")

        # Rough iteration estimates
        total_iterations = simple_count * 1 + medium_count * 2 + complex_count * 4

        if total_iterations <= 5:
            return "Small (5-10 iterations)"
        elif total_iterations <= 15:
            return "Medium (10-20 iterations)"
        else:
            return "Large (20+ iterations)"

    def generate_prd(
        self,
        gap: GeneralizedGap,
        min_stories: int = 5,
        max_stories: int = 15,
        save: bool = True,
    ) -> ImprovementPRD:
        """
        Generate a PRD from a capability gap.

        Args:
            gap: The GeneralizedGap to address
            min_stories: Minimum number of stories to generate
            max_stories: Maximum number of stories to generate
            save: Whether to save the PRD to disk

        Returns:
            Generated ImprovementPRD
        """
        # Generate names
        prd_name = self._generate_prd_name(gap)
        branch_name = self._generate_branch_name(prd_name)

        # Select and customize stories
        templates = self._select_stories(gap, min_stories, max_stories)
        stories = [
            self._customize_story(template, gap, i + 1)
            for i, template in enumerate(templates)
        ]

        # Set dependencies
        self._set_dependencies(stories)

        # Estimate effort
        effort = self._estimate_effort(stories)

        now = datetime.now().isoformat()

        # Create PRD
        prd = ImprovementPRD(
            name=prd_name,
            project=f"claude-loop-improvement-{gap.category.lower()}",
            branchName=branch_name,
            description=(
                f"Improvement PRD to address {gap.category.replace('_', ' ').title()} capability gap. "
                f"Generated from gap analysis: {gap.description[:100]}..."
            ),
            gap_id=gap.gap_id,
            gap_category=gap.category,
            priority_score=gap.priority_score,
            userStories=stories,
            status="pending_review",
            created_at=now,
            updated_at=now,
            estimated_effort=effort,
            affected_task_types=gap.affected_task_types,
            source_patterns=gap.pattern_ids,
        )

        if save:
            self._save_prd(prd)

        return prd

    def generate_prd_by_gap_id(
        self,
        gap_id: str,
        min_stories: int = 5,
        max_stories: int = 15,
        save: bool = True,
    ) -> ImprovementPRD | None:
        """
        Generate a PRD from a gap ID.

        Args:
            gap_id: The gap ID to generate PRD for
            min_stories: Minimum number of stories
            max_stories: Maximum number of stories
            save: Whether to save the PRD

        Returns:
            Generated PRD or None if gap not found
        """
        gap = self.gap_generalizer.get_gap_by_id(gap_id)

        if not gap:
            return None

        return self.generate_prd(gap, min_stories, max_stories, save)

    def _save_prd(self, prd: ImprovementPRD) -> Path:
        """Save PRD to the improvements directory."""
        prd_path = self.improvements_dir / f"{prd.name}.json"

        with open(prd_path, 'w') as f:
            json.dump(prd.to_dict(), f, indent=2)

        return prd_path

    def load_prd(self, prd_name: str) -> ImprovementPRD | None:
        """Load a PRD by name."""
        prd_path = self.improvements_dir / f"{prd_name}.json"

        if not prd_path.exists():
            return None

        try:
            with open(prd_path) as f:
                data = json.load(f)
                return ImprovementPRD.from_dict(data)
        except (json.JSONDecodeError, IOError):
            return None

    def list_prds(
        self,
        status: str | None = None,
    ) -> list[ImprovementPRD]:
        """
        List all improvement PRDs.

        Args:
            status: Filter by status (None for all)

        Returns:
            List of PRDs
        """
        prds = []

        for prd_path in self.improvements_dir.glob("*.json"):
            try:
                with open(prd_path) as f:
                    data = json.load(f)
                    prd = ImprovementPRD.from_dict(data)

                    if status is None or prd.status == status:
                        prds.append(prd)
            except (json.JSONDecodeError, IOError):
                continue

        # Sort by priority score (highest first)
        prds.sort(key=lambda p: p.priority_score, reverse=True)

        return prds

    def get_pending_prds(self) -> list[ImprovementPRD]:
        """Get all PRDs pending review."""
        return self.list_prds(status="pending_review")

    def update_prd_status(
        self,
        prd_name: str,
        status: str,
        notes: str = "",
    ) -> bool:
        """
        Update the status of a PRD.

        Args:
            prd_name: Name of the PRD
            status: New status
            notes: Optional reviewer notes

        Returns:
            True if successful, False if PRD not found
        """
        prd = self.load_prd(prd_name)

        if not prd:
            return False

        prd.status = status
        prd.updated_at = datetime.now().isoformat()

        if status in ["approved", "rejected"]:
            prd.reviewed_at = datetime.now().isoformat()

        if notes:
            prd.reviewer_notes = notes

        self._save_prd(prd)
        return True

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all improvement PRDs."""
        all_prds = self.list_prds()

        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_stories = 0

        for prd in all_prds:
            by_status[prd.status] = by_status.get(prd.status, 0) + 1
            by_category[prd.gap_category] = by_category.get(prd.gap_category, 0) + 1
            total_stories += len(prd.userStories)

        return {
            "total_prds": len(all_prds),
            "by_status": by_status,
            "by_category": by_category,
            "total_stories": total_stories,
            "pending_review": len([p for p in all_prds if p.status == "pending_review"]),
            "approved": len([p for p in all_prds if p.status == "approved"]),
            "in_progress": len([p for p in all_prds if p.status == "in_progress"]),
            "complete": len([p for p in all_prds if p.status == "complete"]),
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Improvement PRD Generator for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/improvement-prd-generator.py generate GAP-ABCD1234
    python lib/improvement-prd-generator.py generate GAP-ABCD1234 --json
    python lib/improvement-prd-generator.py generate GAP-ABCD1234 --min-stories 7 --max-stories 12
    python lib/improvement-prd-generator.py list
    python lib/improvement-prd-generator.py list --status pending_review
    python lib/improvement-prd-generator.py show improve-ui-interaction-abc123
    python lib/improvement-prd-generator.py pending
    python lib/improvement-prd-generator.py summary
    python lib/improvement-prd-generator.py approve improve-ui-interaction-abc123
    python lib/improvement-prd-generator.py reject improve-ui-interaction-abc123 --reason "Needs more detail"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate command
    gen_parser = subparsers.add_parser(
        "generate", help="Generate a PRD from a capability gap"
    )
    gen_parser.add_argument(
        "gap_id",
        type=str,
        help="Gap ID to generate PRD for (e.g., GAP-ABCD1234)",
    )
    gen_parser.add_argument(
        "--min-stories",
        type=int,
        default=5,
        help="Minimum number of stories (default: 5)",
    )
    gen_parser.add_argument(
        "--max-stories",
        type=int,
        default=15,
        help="Maximum number of stories (default: 15)",
    )
    gen_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    gen_parser.add_argument(
        "--no-save", action="store_true",
        help="Don't save to disk",
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List all improvement PRDs"
    )
    list_parser.add_argument(
        "--status",
        choices=["pending_review", "approved", "rejected", "in_progress", "complete", "all"],
        default="all",
        help="Filter by status (default: all)",
    )
    list_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # show command
    show_parser = subparsers.add_parser(
        "show", help="Show details of a specific PRD"
    )
    show_parser.add_argument(
        "prd_name",
        type=str,
        help="PRD name to show",
    )
    show_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # pending command
    pending_parser = subparsers.add_parser(
        "pending", help="List PRDs pending review"
    )
    pending_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # summary command
    summary_parser = subparsers.add_parser(
        "summary", help="Show summary of all PRDs"
    )
    summary_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    # approve command
    approve_parser = subparsers.add_parser(
        "approve", help="Approve a PRD for implementation"
    )
    approve_parser.add_argument(
        "prd_name",
        type=str,
        help="PRD name to approve",
    )
    approve_parser.add_argument(
        "--notes",
        type=str,
        default="",
        help="Reviewer notes",
    )

    # reject command
    reject_parser = subparsers.add_parser(
        "reject", help="Reject a PRD"
    )
    reject_parser.add_argument(
        "prd_name",
        type=str,
        help="PRD name to reject",
    )
    reject_parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Reason for rejection",
    )

    # start command
    start_parser = subparsers.add_parser(
        "start", help="Mark a PRD as in progress"
    )
    start_parser.add_argument(
        "prd_name",
        type=str,
        help="PRD name to start",
    )

    # complete command
    complete_parser = subparsers.add_parser(
        "complete", help="Mark a PRD as complete"
    )
    complete_parser.add_argument(
        "prd_name",
        type=str,
        help="PRD name to mark complete",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize generator
    project_root = Path(__file__).parent.parent
    generator = ImprovementPRDGenerator(project_root=project_root)

    if args.command == "generate":
        save = not args.no_save
        prd = generator.generate_prd_by_gap_id(
            args.gap_id,
            min_stories=args.min_stories,
            max_stories=args.max_stories,
            save=save,
        )

        if not prd:
            print(f"Error: Gap '{args.gap_id}' not found")
            print("\nUse 'gap-generalizer.py list' to see available gaps")
            sys.exit(1)

        if args.json:
            print(json.dumps(prd.to_dict(), indent=2))
        else:
            print(f"=== Generated PRD: {prd.name} ===\n")
            print(f"Project: {prd.project}")
            print(f"Branch: {prd.branchName}")
            print(f"Status: {prd.status}")
            print(f"Gap ID: {prd.gap_id} ({prd.gap_category})")
            print(f"Priority Score: {prd.priority_score:.1f}")
            print(f"Estimated Effort: {prd.estimated_effort}")
            print()
            print(f"Description:")
            print(f"  {prd.description}")
            print()
            print(f"User Stories ({len(prd.userStories)}):")
            print("-" * 70)
            for story in prd.userStories:
                deps = f" [deps: {', '.join(story.dependencies)}]" if story.dependencies else ""
                print(f"  [{story.id}] {story.title}")
                print(f"      Complexity: {story.estimatedComplexity}, Model: {story.suggestedModel}{deps}")
                print(f"      Criteria: {len(story.acceptanceCriteria)} items")
            print()
            print(f"Affected Task Types: {', '.join(prd.affected_task_types[:3])}")
            if save:
                prd_path = generator.improvements_dir / f"{prd.name}.json"
                print(f"\nSaved to: {prd_path}")

    elif args.command == "list":
        status = None if args.status == "all" else args.status
        prds = generator.list_prds(status=status)

        if args.json:
            print(json.dumps([p.to_dict() for p in prds], indent=2))
        else:
            if not prds:
                print(f"No PRDs found with status: {args.status}")
                return

            print(f"{'Name':<40} {'Status':<15} {'Priority':>8}  Stories")
            print("-" * 75)
            for prd in prds:
                print(f"{prd.name:<40} {prd.status:<15} {prd.priority_score:>7.1f}  {len(prd.userStories)}")

    elif args.command == "show":
        prd = generator.load_prd(args.prd_name)

        if not prd:
            print(f"Error: PRD '{args.prd_name}' not found")
            sys.exit(1)

        if args.json:
            print(json.dumps(prd.to_dict(), indent=2))
        else:
            print(f"=== PRD: {prd.name} ===\n")
            print(f"Project: {prd.project}")
            print(f"Branch: {prd.branchName}")
            print(f"Status: {prd.status}")
            print(f"Created: {prd.created_at[:19] if prd.created_at else 'N/A'}")
            print(f"Updated: {prd.updated_at[:19] if prd.updated_at else 'N/A'}")
            if prd.reviewed_at:
                print(f"Reviewed: {prd.reviewed_at[:19]}")
            if prd.reviewer_notes:
                print(f"Reviewer Notes: {prd.reviewer_notes}")
            print()
            print(f"Gap: {prd.gap_id} ({prd.gap_category})")
            print(f"Priority Score: {prd.priority_score:.1f}")
            print(f"Estimated Effort: {prd.estimated_effort}")
            print()
            print(f"Description:")
            print(f"  {prd.description}")
            print()
            print(f"User Stories ({len(prd.userStories)}):")
            print("-" * 70)
            for story in prd.userStories:
                status_icon = "[x]" if story.passes else "[ ]"
                deps = f" [deps: {', '.join(story.dependencies)}]" if story.dependencies else ""
                print(f"  {status_icon} [{story.id}] {story.title}")
                print(f"      {story.description[:60]}...")
                print(f"      Complexity: {story.estimatedComplexity}, Model: {story.suggestedModel}{deps}")
                print(f"      Files: {', '.join(story.fileScope[:2])}")
                print(f"      Acceptance Criteria ({len(story.acceptanceCriteria)}):")
                for criterion in story.acceptanceCriteria[:3]:
                    print(f"        - {criterion}")
                if len(story.acceptanceCriteria) > 3:
                    print(f"        ... and {len(story.acceptanceCriteria) - 3} more")
                print()

            print(f"Affected Task Types: {', '.join(prd.affected_task_types)}")
            print(f"Source Patterns: {', '.join(prd.source_patterns)}")

    elif args.command == "pending":
        prds = generator.get_pending_prds()

        if args.json:
            print(json.dumps([p.to_dict() for p in prds], indent=2))
        else:
            if not prds:
                print("No PRDs pending review.")
                return

            print(f"=== PRDs Pending Review ({len(prds)}) ===\n")
            print(f"{'Name':<40} {'Priority':>8}  {'Category':<20}  Stories")
            print("-" * 80)
            for prd in prds:
                print(f"{prd.name:<40} {prd.priority_score:>7.1f}  {prd.gap_category:<20}  {len(prd.userStories)}")

    elif args.command == "summary":
        summary = generator.get_summary()

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=== Improvement PRD Summary ===\n")
            print(f"Total PRDs: {summary['total_prds']}")
            print(f"Total Stories: {summary['total_stories']}")
            print()
            print("By Status:")
            for status, count in summary.get('by_status', {}).items():
                print(f"  {status}: {count}")
            print()
            print("By Category:")
            for category, count in summary.get('by_category', {}).items():
                print(f"  {category}: {count}")

    elif args.command == "approve":
        success = generator.update_prd_status(args.prd_name, "approved", args.notes)
        if success:
            print(f"PRD '{args.prd_name}' approved.")
        else:
            print(f"Error: PRD '{args.prd_name}' not found")
            sys.exit(1)

    elif args.command == "reject":
        success = generator.update_prd_status(args.prd_name, "rejected", args.reason)
        if success:
            print(f"PRD '{args.prd_name}' rejected.")
        else:
            print(f"Error: PRD '{args.prd_name}' not found")
            sys.exit(1)

    elif args.command == "start":
        success = generator.update_prd_status(args.prd_name, "in_progress")
        if success:
            print(f"PRD '{args.prd_name}' marked as in progress.")
        else:
            print(f"Error: PRD '{args.prd_name}' not found")
            sys.exit(1)

    elif args.command == "complete":
        success = generator.update_prd_status(args.prd_name, "complete")
        if success:
            print(f"PRD '{args.prd_name}' marked as complete.")
        else:
            print(f"Error: PRD '{args.prd_name}' not found")
            sys.exit(1)


if __name__ == "__main__":
    main()
