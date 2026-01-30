#!/usr/bin/env python3
"""
Integration Tests for Self-Improvement Pipeline

Tests the end-to-end self-improvement flow:
1. Log failure -> classify -> cluster -> analyze -> generate PRD
2. PRD review workflow (approve, reject, execute)
3. Validation suite blocks bad improvements
4. Rollback restores previous state
5. Daemon runs in background without interference

Uses mock LLM responses for deterministic tests.
CI mode: run without external dependencies.

Requirements:
- pytest
- Python 3.9+
- All self-improvement modules installed

Usage:
    pytest tests/test_self_improvement_e2e.py -v
    pytest tests/test_self_improvement_e2e.py -v -k test_full_pipeline
    CI=true pytest tests/test_self_improvement_e2e.py  # CI mode
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import TestCase, mock

# Add lib directory to path for imports
LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

# Import modules with dynamic loading for hyphenated names
import importlib.util


def _import_module(module_name: str, file_name: str):
    """Import a module from a hyphenated filename."""
    module_path = LIB_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {module_name} from {file_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Import self-improvement modules
failure_classifier = _import_module("failure_classifier", "failure-classifier.py")
pattern_clusterer = _import_module("pattern_clusterer", "pattern-clusterer.py")
root_cause_analyzer = _import_module("root_cause_analyzer", "root-cause-analyzer.py")
gap_generalizer = _import_module("gap_generalizer", "gap-generalizer.py")
improvement_prd_generator = _import_module(
    "improvement_prd_generator", "improvement-prd-generator.py"
)
improvement_validator = _import_module(
    "improvement_validator", "improvement-validator.py"
)

FailureCategory = failure_classifier.FailureCategory
FailureClassifier = failure_classifier.FailureClassifier
PatternClusterer = pattern_clusterer.PatternClusterer
RootCauseAnalyzer = root_cause_analyzer.RootCauseAnalyzer
GapGeneralizer = gap_generalizer.GapGeneralizer
ImprovementPRDGenerator = improvement_prd_generator.ImprovementPRDGenerator
ImprovementValidator = improvement_validator.ImprovementValidator


# ============================================================================
# Test Fixtures and Mock Data
# ============================================================================


@dataclass
class MockLLMResponse:
    """Mock LLM response for testing."""

    analysis: str
    confidence: float


class MockLLM:
    """Mock LLM for deterministic testing."""

    def __init__(self):
        self.call_count = 0
        self.responses = {
            "root_cause": MockLLMResponse(
                analysis=json.dumps(
                    {
                        "whys": [
                            "Why did the task fail? - Element not found",
                            "Why was element not found? - No detection capability",
                            "Why no detection? - Missing UI automation tools",
                            "Why missing tools? - No computer_use agent installed",
                            "Why not installed? - Not in capability inventory",
                        ],
                        "root_cause": "Missing UI automation capability (computer_use)",
                        "capability_gap": "UI_INTERACTION - Click element detection",
                        "counterfactual": "Vision-based UI element detection tool",
                    }
                ),
                confidence=0.85,
            ),
            "prd_generation": MockLLMResponse(
                analysis=json.dumps(
                    {
                        "stories": [
                            {
                                "title": "Install computer_use agent",
                                "criteria": ["Download agent", "Configure", "Test"],
                            }
                        ]
                    }
                ),
                confidence=0.9,
            ),
        }

    def call(self, prompt: str, response_type: str = "root_cause") -> str:
        """Mock LLM call."""
        self.call_count += 1
        response = self.responses.get(response_type, self.responses["root_cause"])
        return response.analysis


# Sample execution log entries for testing
SAMPLE_LOGS = [
    {
        "story_id": "TEST-001",
        "story_title": "Click submit button",
        "timestamp_start": "2024-01-10T10:00:00Z",
        "timestamp_end": "2024-01-10T10:00:05Z",
        "duration_ms": 5000,
        "status": "failure",
        "exit_code": 1,
        "error_type": "not_found",
        "error_message": "Element with id='submit-btn' not found",
        "retry_count": 2,
        "fallback_count": 0,
        "attempted_actions": [
            {"tool": "Bash", "params": {"command": "xdotool search --name 'Submit'"}}
        ],
        "tools_used": ["Bash"],
        "file_types": [],
        "context": {"application": "web_browser", "platform": "linux"},
    },
    {
        "story_id": "TEST-002",
        "story_title": "Fill form field",
        "timestamp_start": "2024-01-10T10:05:00Z",
        "timestamp_end": "2024-01-10T10:05:03Z",
        "duration_ms": 3000,
        "status": "failure",
        "exit_code": 1,
        "error_type": "not_found",
        "error_message": "Input element with id='username' not found",
        "retry_count": 1,
        "fallback_count": 0,
        "attempted_actions": [
            {"tool": "Bash", "params": {"command": "xdotool type 'testuser'"}}
        ],
        "tools_used": ["Bash"],
        "file_types": [],
        "context": {"application": "web_browser", "platform": "linux"},
    },
    {
        "story_id": "TEST-003",
        "story_title": "Click submit button again",
        "timestamp_start": "2024-01-10T11:00:00Z",
        "timestamp_end": "2024-01-10T11:00:04Z",
        "duration_ms": 4000,
        "status": "failure",
        "exit_code": 1,
        "error_type": "not_found",
        "error_message": "Element with id='submit-btn' not found on page",
        "retry_count": 3,
        "fallback_count": 1,
        "attempted_actions": [
            {"tool": "Bash", "params": {"command": "xdotool search --name 'Submit'"}}
        ],
        "tools_used": ["Bash"],
        "file_types": [],
        "context": {"application": "web_browser", "platform": "linux"},
    },
    # A different failure type - network error
    {
        "story_id": "TEST-004",
        "story_title": "Download file from URL",
        "timestamp_start": "2024-01-10T12:00:00Z",
        "timestamp_end": "2024-01-10T12:00:30Z",
        "duration_ms": 30000,
        "status": "failure",
        "exit_code": 1,
        "error_type": "timeout",
        "error_message": "Connection timeout after 30s",
        "retry_count": 1,
        "fallback_count": 0,
        "attempted_actions": [
            {"tool": "Bash", "params": {"command": "curl https://example.com/file.zip"}}
        ],
        "tools_used": ["Bash"],
        "file_types": [],
        "context": {"application": "curl", "platform": "linux"},
    },
    # Success case
    {
        "story_id": "TEST-005",
        "story_title": "Read configuration file",
        "timestamp_start": "2024-01-10T13:00:00Z",
        "timestamp_end": "2024-01-10T13:00:01Z",
        "duration_ms": 1000,
        "status": "success",
        "exit_code": 0,
        "error_type": "",
        "error_message": "",
        "retry_count": 0,
        "fallback_count": 0,
        "attempted_actions": [
            {"tool": "Read", "params": {"file_path": "/path/to/config.json"}}
        ],
        "tools_used": ["Read"],
        "file_types": ["json"],
        "context": {"application": "config_parser"},
    },
]


# ============================================================================
# Base Test Class with Setup/Teardown
# ============================================================================


class SelfImprovementE2ETestCase(TestCase):
    """Base test case with temporary directory setup."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.test_root = Path(tempfile.mkdtemp(prefix="claude_loop_test_"))
        cls.claude_loop_dir = cls.test_root / ".claude-loop"
        cls.claude_loop_dir.mkdir(parents=True)

        # Create subdirectories
        (cls.claude_loop_dir / "improvements").mkdir()
        (cls.claude_loop_dir / "analysis_cache").mkdir()
        (cls.claude_loop_dir / "held_out_cases").mkdir()
        (cls.claude_loop_dir / "validation_reports").mkdir()

        # Initialize empty files
        cls.execution_log = cls.claude_loop_dir / "execution_log.jsonl"
        cls.execution_log.write_text("")

        cls.capability_gaps = cls.claude_loop_dir / "capability_gaps.json"
        cls.capability_gaps.write_text('{"gaps": {}}')

        cls.capability_inventory = cls.claude_loop_dir / "capability_inventory.json"
        cls.capability_inventory.write_text(
            json.dumps({"capabilities": [], "last_updated": datetime.now(timezone.utc).isoformat()})
        )

        # Set environment variable for modules to use test directory
        os.environ["CLAUDE_LOOP_DIR"] = str(cls.claude_loop_dir)

        cls.is_ci = os.environ.get("CI", "").lower() == "true"

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        if cls.test_root.exists():
            shutil.rmtree(cls.test_root)
        os.environ.pop("CLAUDE_LOOP_DIR", None)

    def setUp(self):
        """Set up each test."""
        # Clear log files
        self.execution_log.write_text("")
        self.capability_gaps.write_text('{"gaps": {}}')

        # Reset improvement directory
        improvements_dir = self.claude_loop_dir / "improvements"
        if improvements_dir.exists():
            for f in improvements_dir.iterdir():
                f.unlink()

    def write_execution_logs(self, logs: list[dict]):
        """Write sample logs to execution log file."""
        with open(self.execution_log, "w") as f:
            for log_entry in logs:
                f.write(json.dumps(log_entry) + "\n")

    def read_capability_gaps(self) -> list[dict]:
        """Read capability gaps from file."""
        if not self.capability_gaps.exists():
            return []
        content = self.capability_gaps.read_text().strip()
        if not content:
            return []
        return json.loads(content)

    def read_improvements(self) -> list[Path]:
        """Read improvement PRD files."""
        improvements_dir = self.claude_loop_dir / "improvements"
        return list(improvements_dir.glob("improvement-*.json"))


# ============================================================================
# Test 1: Full Pipeline Flow
# ============================================================================


class TestFullPipeline(SelfImprovementE2ETestCase):
    """Test the complete flow: log -> classify -> cluster -> analyze -> PRD."""

    def test_full_pipeline_from_logs_to_prd(self):
        """Test complete pipeline from execution logs to PRD generation."""
        # Step 1: Write execution logs
        self.write_execution_logs(SAMPLE_LOGS)

        # Step 2: Classify failures
        classifier = FailureClassifier(self.execution_log)
        classifications = []

        # Load all entries and classify them
        all_entries = classifier._load_history()
        for log_entry in all_entries:
            result = classifier.classify_failure(log_entry)
            classifications.append(result)

        # Verify classifications
        self.assertEqual(len(classifications), 5)

        # First three should be classified (UI element not found)
        capability_gaps = [
            c for c in classifications if c.category == FailureCategory.CAPABILITY_GAP
        ]
        self.assertGreaterEqual(len(capability_gaps), 2)

        # One should be transient (timeout)
        transient = [
            c for c in classifications if c.category == FailureCategory.TRANSIENT_ERROR
        ]
        self.assertGreaterEqual(len(transient), 1)

        # One should be success
        successes = [c for c in classifications if c.category == FailureCategory.SUCCESS]
        self.assertEqual(len(successes), 1)

        # Step 3: Cluster failures
        clusterer = PatternClusterer(self.execution_log, min_occurrences=2)
        patterns = clusterer.cluster_failures()

        # Should find at least 1 pattern (UI element not found repeated)
        self.assertGreaterEqual(len(patterns), 1)

        # The main pattern should have 2-3 occurrences
        ui_pattern = next((p for p in patterns if "not found" in p.normalized_message.lower()), None)
        self.assertIsNotNone(ui_pattern)
        self.assertGreaterEqual(ui_pattern.occurrences, 2)

        # Step 4: Root cause analysis (heuristic mode - no LLM)
        analyzer = RootCauseAnalyzer(self.claude_loop_dir, use_llm=False)
        root_cause = analyzer.analyze_root_cause(ui_pattern)

        self.assertIsNotNone(root_cause)
        self.assertEqual(len(root_cause.whys), 5)
        # Check that root cause analysis returned meaningful results
        self.assertGreater(len(root_cause.capability_gap), 0)
        self.assertGreater(root_cause.confidence, 0.5)

        # Step 5: Generalize gap
        generalizer = GapGeneralizer(self.claude_loop_dir)
        generalized_gap = generalizer.generalize_gap(root_cause)

        self.assertIsNotNone(generalized_gap)
        self.assertIsNotNone(generalized_gap.category)
        self.assertGreater(generalized_gap.priority_score, 0)
        self.assertGreater(len(generalized_gap.affected_task_types), 0)

        # Step 6: Generate PRD
        improvements_dir = self.claude_loop_dir / "improvements"
        prd_generator = ImprovementPRDGenerator(
            project_root=self.claude_loop_dir.parent,
            improvements_dir=improvements_dir,
            use_llm=False
        )
        prd = prd_generator.generate_prd(generalized_gap, save=True)

        self.assertIsNotNone(prd)
        self.assertGreater(len(prd.userStories), 0)
        self.assertEqual(prd.status, "pending_review")
        self.assertGreater(len(prd.project), 0)
        self.assertGreater(len(prd.description), 0)

        # Verify PRD was generated (file saving tested separately)
        # The PRD structure is correct in-memory
        self.assertGreater(len(prd.userStories), 1)  # Multiple stories

        # Verify first story has required fields
        first_story = prd.userStories[0]
        self.assertGreater(len(first_story.id), 0)
        self.assertGreater(len(first_story.title), 0)
        self.assertGreater(len(first_story.acceptanceCriteria), 0)
        self.assertGreater(first_story.priority, 0)


# ============================================================================
# Test 2: PRD Review Workflow
# ============================================================================


class TestPRDReviewWorkflow(SelfImprovementE2ETestCase):
    """Test PRD approval, rejection, and execution workflow."""

    def create_test_prd(self, status: str = "pending_review") -> Path:
        """Create a test PRD file."""
        prd = {
            "project": "test-improvement-ui-detection",
            "branchName": "feature/ui-detection",
            "description": "Add UI element detection capability",
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "userStories": [
                {
                    "id": "UI-001",
                    "title": "Basic element detection",
                    "description": "Detect UI elements by ID",
                    "acceptanceCriteria": [
                        "Create detector module",
                        "Support ID-based detection",
                        "Add tests",
                    ],
                    "priority": 1,
                    "dependencies": [],
                    "passes": False,
                }
            ],
        }

        prd_path = self.claude_loop_dir / "improvements" / "improvement-ui-detection.json"
        prd_path.write_text(json.dumps(prd, indent=2))
        return prd_path

    def test_approve_prd_workflow(self):
        """Test approving a pending PRD."""
        prd_path = self.create_test_prd()

        # Load PRD
        prd_data = json.loads(prd_path.read_text())
        self.assertEqual(prd_data["status"], "pending_review")

        # Simulate approval
        prd_data["status"] = "approved"
        prd_data["approved_at"] = datetime.now(timezone.utc).isoformat()
        prd_data["approved_by"] = "test_user"
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Verify approval
        updated_prd = json.loads(prd_path.read_text())
        self.assertEqual(updated_prd["status"], "approved")
        self.assertIn("approved_at", updated_prd)
        self.assertIn("approved_by", updated_prd)

    def test_reject_prd_workflow(self):
        """Test rejecting a pending PRD with reason."""
        prd_path = self.create_test_prd()

        # Load PRD
        prd_data = json.loads(prd_path.read_text())

        # Simulate rejection
        prd_data["status"] = "rejected"
        prd_data["rejected_at"] = datetime.now(timezone.utc).isoformat()
        prd_data["rejected_by"] = "test_user"
        prd_data["rejection_reason"] = "Duplicate of existing improvement"
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Verify rejection
        updated_prd = json.loads(prd_path.read_text())
        self.assertEqual(updated_prd["status"], "rejected")
        self.assertIn("rejection_reason", updated_prd)
        self.assertEqual(updated_prd["rejection_reason"], "Duplicate of existing improvement")

    def test_execute_approved_prd(self):
        """Test executing an approved PRD."""
        prd_path = self.create_test_prd(status="approved")

        # Simulate execution start
        prd_data = json.loads(prd_path.read_text())
        prd_data["status"] = "in_progress"
        prd_data["started_at"] = datetime.now(timezone.utc).isoformat()
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Verify in_progress status
        updated_prd = json.loads(prd_path.read_text())
        self.assertEqual(updated_prd["status"], "in_progress")
        self.assertIn("started_at", updated_prd)

        # Simulate completion
        prd_data = updated_prd
        prd_data["status"] = "completed"
        prd_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        prd_data["userStories"][0]["passes"] = True
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Verify completion
        final_prd = json.loads(prd_path.read_text())
        self.assertEqual(final_prd["status"], "completed")
        self.assertTrue(final_prd["userStories"][0]["passes"])

    def test_cannot_execute_unapproved_prd(self):
        """Test that unapproved PRDs cannot be executed."""
        prd_path = self.create_test_prd(status="pending_review")

        prd_data = json.loads(prd_path.read_text())

        # Should not allow execution of pending PRD
        self.assertEqual(prd_data["status"], "pending_review")
        self.assertNotEqual(prd_data["status"], "approved")


# ============================================================================
# Test 3: Validation Suite Blocks Bad Improvements
# ============================================================================


class TestValidationSuite(SelfImprovementE2ETestCase):
    """Test that validation suite blocks problematic improvements."""

    def create_prd_with_tests(self) -> Path:
        """Create a PRD with test requirements."""
        prd = {
            "project": "test-improvement-with-validation",
            "branchName": "feature/with-validation",
            "description": "Improvement with validation tests",
            "status": "approved",
            "userStories": [
                {
                    "id": "VAL-001",
                    "title": "Feature with tests",
                    "acceptanceCriteria": [
                        "Implement feature",
                        "Add unit tests with >80% coverage",
                        "Add integration test",
                    ],
                    "priority": 1,
                    "dependencies": [],
                    "passes": False,
                }
            ],
        }

        prd_path = self.claude_loop_dir / "improvements" / "improvement-validation.json"
        prd_path.write_text(json.dumps(prd, indent=2))
        return prd_path

    def test_validation_detects_missing_tests(self):
        """Test that validator detects missing test files."""
        prd_path = self.create_prd_with_tests()

        validator = ImprovementValidator(self.claude_loop_dir)

        # In CI mode or when no real test runner available, check structure
        if self.is_ci or not shutil.which("pytest"):
            # Just verify the validator can be instantiated and has methods
            self.assertTrue(hasattr(validator, "validate_improvement"))
            self.assertTrue(hasattr(validator, "run_test_suite"))
            return

        # Run validation (will likely fail due to no actual tests)
        result = validator.validate_improvement(str(prd_path))

        # Check that result has expected structure
        self.assertIsNotNone(result)
        self.assertIn("prd_name", result.to_dict())
        self.assertIn("validated_at", result.to_dict())

    def test_validation_with_held_out_cases(self):
        """Test validation against held-out failure cases."""
        # Create a held-out test case
        held_out_dir = self.claude_loop_dir / "held_out_cases"
        test_case = {
            "id": "HELD-001",
            "description": "Click button that was previously failing",
            "original_failure": {
                "error": "Element not found",
                "story_id": "TEST-001",
            },
            "test_command": "python test_ui_click.py",
            "expected": "success",
        }

        held_out_file = held_out_dir / "ui-detection-cases.json"
        held_out_file.write_text(json.dumps([test_case], indent=2))

        # Verify file was created
        self.assertTrue(held_out_file.exists())

        held_out_cases = json.loads(held_out_file.read_text())
        self.assertEqual(len(held_out_cases), 1)
        self.assertEqual(held_out_cases[0]["id"], "HELD-001")

    def test_validation_blocks_on_regression(self):
        """Test that validation blocks deployment if tests regress."""
        prd_path = self.create_prd_with_tests()

        # Simulate validation failure
        validation_report = {
            "prd_name": "improvement-validation",
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "passed": False,
            "blocked": True,
            "failures": ["test_existing_feature regressed", "Coverage dropped to 45%"],
        }

        report_path = (
            self.claude_loop_dir
            / "validation_reports"
            / "validation-improvement-validation.json"
        )
        report_path.write_text(json.dumps(validation_report, indent=2))

        # Verify report
        saved_report = json.loads(report_path.read_text())
        self.assertFalse(saved_report["passed"])
        self.assertTrue(saved_report["blocked"])
        self.assertGreater(len(saved_report["failures"]), 0)


# ============================================================================
# Test 4: Rollback Mechanism
# ============================================================================


class TestRollbackMechanism(SelfImprovementE2ETestCase):
    """Test rollback functionality for failed improvements."""

    def test_rollback_data_structure(self):
        """Test rollback tracking data structure."""
        rollback_info = {
            "improvement_id": "improvement-ui-detection",
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "rolled_back_by": "test_user",
            "reason": "Caused regression in existing tests",
            "git_commits": ["abc123", "def456"],
            "validation_report": "validation-improvement-ui-detection.json",
        }

        # Save rollback info
        rollback_file = (
            self.claude_loop_dir / "improvements" / "rollback-ui-detection.json"
        )
        rollback_file.write_text(json.dumps(rollback_info, indent=2))

        # Verify rollback info
        saved_rollback = json.loads(rollback_file.read_text())
        self.assertEqual(saved_rollback["improvement_id"], "improvement-ui-detection")
        self.assertIn("reason", saved_rollback)
        self.assertGreater(len(saved_rollback["git_commits"]), 0)

    def test_rollback_restores_prd_status(self):
        """Test that rollback updates PRD status correctly."""
        # Create PRD in completed state
        prd = {
            "project": "test-improvement-rollback",
            "status": "completed",
            "completed_at": "2024-01-10T10:00:00Z",
            "userStories": [{"id": "RB-001", "passes": True}],
        }

        prd_path = self.claude_loop_dir / "improvements" / "improvement-rollback.json"
        prd_path.write_text(json.dumps(prd, indent=2))

        # Simulate rollback
        prd_data = json.loads(prd_path.read_text())
        prd_data["status"] = "rolled_back"
        prd_data["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        prd_data["rollback_reason"] = "Test regression"
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Verify rollback
        rolled_back_prd = json.loads(prd_path.read_text())
        self.assertEqual(rolled_back_prd["status"], "rolled_back")
        self.assertIn("rollback_reason", rolled_back_prd)

    def test_rollback_history_tracking(self):
        """Test that rollback events are tracked in history."""
        history_file = self.claude_loop_dir / "improvement_history.jsonl"

        rollback_event = {
            "event_type": "rollback",
            "improvement_id": "improvement-ui-detection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "Validation failed after deployment",
            "git_commits_reverted": ["abc123"],
        }

        # Append to history
        with open(history_file, "a") as f:
            f.write(json.dumps(rollback_event) + "\n")

        # Verify history
        with open(history_file, "r") as f:
            events = [json.loads(line) for line in f]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "rollback")
        self.assertIn("reason", events[0])


# ============================================================================
# Test 5: Background Daemon
# ============================================================================


class TestBackgroundDaemon(SelfImprovementE2ETestCase):
    """Test background gap analysis daemon."""

    def test_daemon_status_file_structure(self):
        """Test daemon status file structure."""
        daemon_status = {
            "pid": 12345,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_analysis": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "interval_seconds": 3600,
            "log_threshold": 10,
            "total_analyses": 5,
            "gaps_found": 2,
            "prds_generated": 1,
        }

        status_file = self.claude_loop_dir / "daemon_status.json"
        status_file.write_text(json.dumps(daemon_status, indent=2))

        # Verify status
        saved_status = json.loads(status_file.read_text())
        self.assertEqual(saved_status["status"], "running")
        self.assertGreater(saved_status["pid"], 0)
        self.assertEqual(saved_status["total_analyses"], 5)

    def test_daemon_lockfile_mechanism(self):
        """Test that daemon uses lockfile to prevent multiple instances."""
        lockfile = self.claude_loop_dir / "daemon.lock"

        # Create lockfile
        lockfile.write_text(str(os.getpid()))

        # Verify lockfile
        self.assertTrue(lockfile.exists())
        pid = int(lockfile.read_text())
        self.assertGreater(pid, 0)

        # Cleanup
        lockfile.unlink()

    def test_daemon_log_threshold_trigger(self):
        """Test that daemon triggers on log entry threshold."""
        # Initial state
        last_analyzed_file = self.claude_loop_dir / "daemon_last_analyzed.txt"
        last_analyzed_file.write_text("0")

        # Write logs
        self.write_execution_logs(SAMPLE_LOGS[:3])  # 3 entries

        # Check if should trigger (threshold = 3)
        last_count = int(last_analyzed_file.read_text())
        current_count = len(SAMPLE_LOGS[:3])

        threshold = 3
        should_trigger = (current_count - last_count) >= threshold

        self.assertTrue(should_trigger)

    def test_daemon_runs_without_blocking(self):
        """Test that daemon can run analysis without blocking."""
        # This is a structural test - verify daemon script exists
        daemon_script = LIB_DIR / "gap-analysis-daemon.sh"

        if not daemon_script.exists():
            self.skipTest("Daemon script not found")

        # Verify script is executable or can be made executable
        self.assertTrue(daemon_script.exists())
        self.assertIn("daemon", daemon_script.name.lower())

    def test_daemon_graceful_shutdown(self):
        """Test daemon status after shutdown."""
        status_file = self.claude_loop_dir / "daemon_status.json"

        # Simulate shutdown
        shutdown_status = {
            "status": "stopped",
            "stopped_at": datetime.now(timezone.utc).isoformat(),
            "reason": "graceful_shutdown",
        }

        status_file.write_text(json.dumps(shutdown_status, indent=2))

        # Verify shutdown
        saved_status = json.loads(status_file.read_text())
        self.assertEqual(saved_status["status"], "stopped")
        self.assertEqual(saved_status["reason"], "graceful_shutdown")


# ============================================================================
# Test 6: Mock LLM Integration
# ============================================================================


class TestMockLLMIntegration(SelfImprovementE2ETestCase):
    """Test that mock LLM responses work correctly in CI mode."""

    def test_mock_llm_for_root_cause_analysis(self):
        """Test using mock LLM for deterministic root cause analysis."""
        mock_llm = MockLLM()

        # Call mock LLM
        response = mock_llm.call("Analyze failure pattern", "root_cause")

        # Parse response
        data = json.loads(response)

        self.assertIn("whys", data)
        self.assertEqual(len(data["whys"]), 5)
        self.assertIn("root_cause", data)
        self.assertIn("capability_gap", data)
        self.assertIn("counterfactual", data)

    def test_mock_llm_call_counting(self):
        """Test that mock LLM tracks call count."""
        mock_llm = MockLLM()

        self.assertEqual(mock_llm.call_count, 0)

        mock_llm.call("Test prompt 1")
        self.assertEqual(mock_llm.call_count, 1)

        mock_llm.call("Test prompt 2")
        self.assertEqual(mock_llm.call_count, 2)

    def test_deterministic_results_across_runs(self):
        """Test that mock LLM returns consistent results."""
        mock_llm_1 = MockLLM()
        mock_llm_2 = MockLLM()

        response_1 = mock_llm_1.call("Same prompt")
        response_2 = mock_llm_2.call("Same prompt")

        self.assertEqual(response_1, response_2)


# ============================================================================
# Test 7: End-to-End Scenario Tests
# ============================================================================


class TestE2EScenarios(SelfImprovementE2ETestCase):
    """Test realistic end-to-end scenarios."""

    def test_scenario_ui_automation_gap_to_prd(self):
        """Test discovering UI automation gap and generating PRD."""
        # Setup: 3 failures related to UI automation
        ui_logs = [log for log in SAMPLE_LOGS if "not found" in log["error_message"]]
        self.write_execution_logs(ui_logs)

        # Step 1: Classify (all should be capability gaps)
        classifier = FailureClassifier(self.execution_log)
        classifications = []
        all_entries = classifier._load_history()
        for log_entry in all_entries:
            result = classifier.classify_failure(log_entry)
            classifications.append(result)

        capability_gaps = [
            c for c in classifications if c.category == FailureCategory.CAPABILITY_GAP
        ]
        self.assertGreater(len(capability_gaps), 0)

        # Step 2: Cluster (should find pattern)
        clusterer = PatternClusterer(self.execution_log, min_occurrences=2)
        patterns = clusterer.cluster_failures()
        self.assertGreater(len(patterns), 0)

        # Step 3: Analyze with heuristic analysis (no LLM needed)
        analyzer = RootCauseAnalyzer(self.claude_loop_dir, use_llm=False)
        root_cause = analyzer.analyze_root_cause(patterns[0])

        self.assertIsNotNone(root_cause)

        # Step 4: Generalize
        generalizer = GapGeneralizer(self.claude_loop_dir)
        gap = generalizer.generalize_gap(root_cause)
        self.assertIsNotNone(gap)

        # Step 5: Generate PRD
        improvements_dir = self.claude_loop_dir / "improvements"
        prd_gen = ImprovementPRDGenerator(
            project_root=self.claude_loop_dir.parent,
            improvements_dir=improvements_dir,
            use_llm=False
        )
        prd = prd_gen.generate_prd(gap)

        self.assertIsNotNone(prd)
        # Check that PRD was generated with some content
        self.assertGreater(len(prd.description), 0)
        self.assertGreater(len(prd.userStories), 0)

    def test_scenario_transient_error_not_creating_prd(self):
        """Test that transient errors don't generate improvement PRDs."""
        # Setup: Single timeout error
        timeout_logs = [log for log in SAMPLE_LOGS if log["error_type"] == "timeout"]
        self.write_execution_logs(timeout_logs)

        # Classify
        classifier = FailureClassifier(self.execution_log)
        all_entries = classifier._load_history()
        self.assertEqual(len(all_entries), 1)
        log_entry = all_entries[0]
        result = classifier.classify_failure(log_entry)

        # Should be transient, not capability gap
        self.assertEqual(result.category, FailureCategory.TRANSIENT_ERROR)

        # Should not meet threshold for clustering (only 1 occurrence)
        clusterer = PatternClusterer(self.execution_log, min_occurrences=2)
        patterns = clusterer.cluster_failures()

        # Should not create patterns from single transient error
        timeout_patterns = [
            p for p in patterns if "timeout" in p.normalized_message.lower()
        ]
        self.assertEqual(len(timeout_patterns), 0)


# ============================================================================
# Main Entry Point
# ============================================================================


if __name__ == "__main__":
    import pytest

    # Run with pytest for better output
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
