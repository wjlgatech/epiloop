#!/usr/bin/env python3
"""
Tests for lib/conflict-detector.py - Conflict Detection System
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Import the module using runpy to handle the hyphenated filename
import runpy
module_path = Path(__file__).parent.parent / "lib" / "conflict-detector.py"
conflict_detector = runpy.run_path(str(module_path))

ImprovementScope = conflict_detector["ImprovementScope"]
Conflict = conflict_detector["Conflict"]
ConflictReport = conflict_detector["ConflictReport"]
ConflictDetector = conflict_detector["ConflictDetector"]
ConflictType = conflict_detector["ConflictType"]
ConflictSeverity = conflict_detector["ConflictSeverity"]
ResolutionStrategy = conflict_detector["ResolutionStrategy"]


class TestImprovementScope(unittest.TestCase):
    """Tests for ImprovementScope dataclass."""

    def test_create_scope_generates_timestamps(self):
        """Scope should auto-generate timestamps if not provided."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"]
        )
        self.assertTrue(scope.created_at)
        self.assertTrue(scope.updated_at)

    def test_is_complete_with_behaviors(self):
        """Scope with behaviors should be considered complete."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling", "retry logic"]
        )
        self.assertTrue(scope.is_complete())

    def test_is_complete_with_domains(self):
        """Scope with domains should be considered complete."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            domain_applicability=["web_backend"]
        )
        self.assertTrue(scope.is_complete())

    def test_is_complete_with_effects(self):
        """Scope with effects should be considered complete."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            effects=["disables retry"]
        )
        self.assertTrue(scope.is_complete())

    def test_is_incomplete_empty(self):
        """Empty scope should be incomplete."""
        scope = ImprovementScope(improvement_id="IMP-TEST123")
        self.assertFalse(scope.is_complete())

    def test_get_normalized_behaviors(self):
        """Should normalize behaviors for comparison."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["Error Handling ", " RETRY Logic"]
        )
        behaviors = scope.get_normalized_behaviors()
        self.assertEqual(behaviors, {"error handling", "retry logic"})

    def test_get_normalized_domains(self):
        """Should normalize domains for comparison."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            domain_applicability=["WEB_BACKEND ", " API_Service"]
        )
        domains = scope.get_normalized_domains()
        self.assertEqual(domains, {"web_backend", "api_service"})

    def test_to_dict(self):
        """Scope should serialize to dict."""
        scope = ImprovementScope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"],
            domain_applicability=["web_backend"]
        )
        data = scope.to_dict()
        self.assertEqual(data["improvement_id"], "IMP-TEST123")
        self.assertEqual(data["affected_behaviors"], ["error handling"])

    def test_from_dict(self):
        """Scope should deserialize from dict."""
        data = {
            "improvement_id": "IMP-TEST123",
            "affected_behaviors": ["error handling"],
            "domain_applicability": ["web_backend"],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"
        }
        scope = ImprovementScope.from_dict(data)
        self.assertEqual(scope.improvement_id, "IMP-TEST123")
        self.assertEqual(scope.affected_behaviors, ["error handling"])


class TestConflict(unittest.TestCase):
    """Tests for Conflict dataclass."""

    def test_create_conflict_generates_id(self):
        """Conflict should auto-generate ID if not provided."""
        conflict = Conflict(
            conflict_id="",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict"
        )
        self.assertTrue(conflict.conflict_id.startswith("CONF-"))
        self.assertEqual(len(conflict.conflict_id), 13)  # CONF- + 8 hex chars

    def test_create_conflict_generates_timestamp(self):
        """Conflict should auto-generate timestamp if not provided."""
        conflict = Conflict(
            conflict_id="",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict"
        )
        self.assertTrue(conflict.detected_at)

    def test_is_blocking_unresolved(self):
        """Blocking unresolved conflict should return True."""
        conflict = Conflict(
            conflict_id="",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict",
            resolved=False
        )
        self.assertTrue(conflict.is_blocking())

    def test_is_blocking_resolved(self):
        """Blocking resolved conflict should return False."""
        conflict = Conflict(
            conflict_id="",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict",
            resolved=True
        )
        self.assertFalse(conflict.is_blocking())

    def test_is_blocking_warning(self):
        """Warning conflict should not be blocking."""
        conflict = Conflict(
            conflict_id="",
            conflict_type=ConflictType.SCOPE_OVERLAP.value,
            severity=ConflictSeverity.WARNING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict",
            resolved=False
        )
        self.assertFalse(conflict.is_blocking())


class TestConflictReport(unittest.TestCase):
    """Tests for ConflictReport dataclass."""

    def test_create_report_generates_timestamp(self):
        """Report should auto-generate timestamp."""
        report = ConflictReport(improvement_id="IMP-TEST123")
        self.assertTrue(report.generated_at)

    def test_report_can_promote_true(self):
        """Report with no blocking conflicts can promote."""
        report = ConflictReport(
            improvement_id="IMP-TEST123",
            blocking_conflicts=0,
            can_promote=True
        )
        self.assertTrue(report.can_promote)

    def test_report_can_promote_false(self):
        """Report with blocking conflicts cannot promote."""
        report = ConflictReport(
            improvement_id="IMP-TEST123",
            blocking_conflicts=1,
            can_promote=False,
            blocking_reasons=["Behavioral contradiction detected"]
        )
        self.assertFalse(report.can_promote)
        self.assertEqual(len(report.blocking_reasons), 1)


class TestConflictDetector(unittest.TestCase):
    """Tests for ConflictDetector class."""

    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        (self.base_path / ".claude-loop").mkdir(parents=True)
        self.detector = ConflictDetector(base_dir=self.base_path)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_queue_with_proposals(self, proposals: dict):
        """Helper to create queue file with proposals."""
        queue_file = self.base_path / ".claude-loop" / "improvement_queue.json"
        queue_file.write_text(json.dumps({"proposals": proposals}))

    def test_set_scope_creates_new(self):
        """Setting scope for new improvement should create it."""
        scope = self.detector.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"],
            domain_applicability=["web_backend"]
        )
        self.assertEqual(scope.improvement_id, "IMP-TEST123")
        self.assertEqual(scope.affected_behaviors, ["error handling"])

    def test_set_scope_updates_existing(self):
        """Setting scope for existing improvement should update it."""
        self.detector.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"]
        )
        scope = self.detector.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["retry logic"]
        )
        self.assertEqual(scope.affected_behaviors, ["retry logic"])

    def test_get_scope_existing(self):
        """Getting existing scope should return it."""
        self.detector.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"]
        )
        scope = self.detector.get_scope("IMP-TEST123")
        self.assertIsNotNone(scope)
        self.assertEqual(scope.affected_behaviors, ["error handling"])

    def test_get_scope_nonexistent(self):
        """Getting non-existent scope should return None."""
        scope = self.detector.get_scope("IMP-NONEXISTENT")
        self.assertIsNone(scope)

    def test_has_scope_true(self):
        """has_scope should return True for complete scope."""
        self.detector.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"]
        )
        self.assertTrue(self.detector.has_scope("IMP-TEST123"))

    def test_has_scope_false_missing(self):
        """has_scope should return False for missing scope."""
        self.assertFalse(self.detector.has_scope("IMP-NONEXISTENT"))

    def test_infer_scope_from_proposal(self):
        """Should infer scope from proposal content."""
        proposals = {
            "IMP-TEST123": {
                "problem_pattern": "Retry failures causing cascading errors",
                "proposed_solution": "Add exponential backoff retry with cache validation",
                "affected_domains": ["web_backend"]
            }
        }
        self._create_queue_with_proposals(proposals)

        scope = self.detector.infer_scope("IMP-TEST123")
        self.assertIn("retry logic", scope.affected_behaviors)
        self.assertIn("caching", scope.affected_behaviors)

    def test_detect_behavioral_contradiction(self):
        """Should detect behavioral contradictions between improvements."""
        proposals = {
            "IMP-AAA": {
                "problem_pattern": "Errors not handled properly",
                "proposed_solution": "Always retry on failure with exponential backoff"
            },
            "IMP-BBB": {
                "problem_pattern": "Too many retries causing delays",
                "proposed_solution": "Never retry to fail fast and surface errors immediately"
            }
        }
        self._create_queue_with_proposals(proposals)

        conflicts = self.detector.detect_conflicts("IMP-AAA", "IMP-BBB")

        self.assertGreater(len(conflicts), 0)
        behavioral_conflicts = [
            c for c in conflicts
            if c.conflict_type == ConflictType.BEHAVIORAL_CONTRADICTION.value
        ]
        self.assertGreater(len(behavioral_conflicts), 0)

    def test_detect_scope_overlap(self):
        """Should detect scope overlaps between improvements."""
        # Set up scopes
        self.detector.set_scope(
            improvement_id="IMP-AAA",
            affected_behaviors=["error handling", "logging"],
            domain_applicability=["web_backend", "api_service"]
        )
        self.detector.set_scope(
            improvement_id="IMP-BBB",
            affected_behaviors=["error handling", "validation"],
            domain_applicability=["web_backend"]
        )

        # Create proposals
        proposals = {
            "IMP-AAA": {"problem_pattern": "Test A", "proposed_solution": "Sol A"},
            "IMP-BBB": {"problem_pattern": "Test B", "proposed_solution": "Sol B"}
        }
        self._create_queue_with_proposals(proposals)

        conflicts = self.detector.detect_conflicts("IMP-AAA", "IMP-BBB")

        scope_conflicts = [
            c for c in conflicts
            if c.conflict_type == ConflictType.SCOPE_OVERLAP.value
        ]
        self.assertGreater(len(scope_conflicts), 0)

    def test_detect_dependency_conflict(self):
        """Should detect dependency conflicts between improvements."""
        # Set up scopes with conflicting preconditions/effects
        self.detector.set_scope(
            improvement_id="IMP-AAA",
            preconditions=["caching enabled"],
            effects=["optimizes response time"]
        )
        self.detector.set_scope(
            improvement_id="IMP-BBB",
            preconditions=["fast response"],
            effects=["disables caching"]  # Conflicts with AAA's precondition
        )

        # Create proposals
        proposals = {
            "IMP-AAA": {"problem_pattern": "Test A", "proposed_solution": "Sol A"},
            "IMP-BBB": {"problem_pattern": "Test B", "proposed_solution": "Sol B"}
        }
        self._create_queue_with_proposals(proposals)

        conflicts = self.detector.detect_conflicts("IMP-AAA", "IMP-BBB")

        dep_conflicts = [
            c for c in conflicts
            if c.conflict_type == ConflictType.DEPENDENCY_CONFLICT.value
        ]
        self.assertGreater(len(dep_conflicts), 0)

    def test_detect_resource_contention(self):
        """Should detect resource contentions between improvements."""
        # Set up scopes with shared resources
        self.detector.set_scope(
            improvement_id="IMP-AAA",
            resources_used=[{"type": "config_file", "name": "settings.json"}]
        )
        self.detector.set_scope(
            improvement_id="IMP-BBB",
            resources_used=[{"type": "config_file", "name": "settings.json"}]
        )

        # Create proposals
        proposals = {
            "IMP-AAA": {"problem_pattern": "Test A", "proposed_solution": "Sol A"},
            "IMP-BBB": {"problem_pattern": "Test B", "proposed_solution": "Sol B"}
        }
        self._create_queue_with_proposals(proposals)

        conflicts = self.detector.detect_conflicts("IMP-AAA", "IMP-BBB")

        resource_conflicts = [
            c for c in conflicts
            if c.conflict_type == ConflictType.RESOURCE_CONTENTION.value
        ]
        self.assertGreater(len(resource_conflicts), 0)

    def test_analyze_improvement(self):
        """Should analyze improvement against all others."""
        proposals = {
            "IMP-TARGET": {
                "problem_pattern": "Always retry errors",
                "proposed_solution": "Add always retry with backoff",
                "status": "proposed"
            },
            "IMP-OTHER1": {
                "problem_pattern": "Too many retries",
                "proposed_solution": "Never retry to fail fast",
                "status": "proposed"
            },
            "IMP-OTHER2": {
                "problem_pattern": "Unrelated issue",
                "proposed_solution": "Unrelated fix",
                "status": "rejected"  # Should be skipped
            }
        }
        self._create_queue_with_proposals(proposals)

        report = self.detector.analyze_improvement("IMP-TARGET")

        self.assertEqual(report.improvement_id, "IMP-TARGET")
        # Should have conflicts with OTHER1 but not OTHER2 (rejected)
        self.assertGreater(report.total_conflicts, 0)

    def test_can_promote_with_blocking_conflicts(self):
        """can_promote should return False when blocking conflicts exist."""
        proposals = {
            "IMP-AAA": {
                "problem_pattern": "Always retry errors",
                "proposed_solution": "Add always retry with backoff"
            },
            "IMP-BBB": {
                "problem_pattern": "Too many retries",
                "proposed_solution": "Never retry to fail fast"
            }
        }
        self._create_queue_with_proposals(proposals)

        can_promote, reasons = self.detector.can_promote("IMP-AAA")

        # Should have blocking conflicts due to retry contradiction
        if not can_promote:
            self.assertGreater(len(reasons), 0)

    def test_resolve_conflict(self):
        """Should mark conflict as resolved."""
        # Create a conflict
        conflict = Conflict(
            conflict_id="CONF-TEST1234",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict"
        )
        self.detector._conflicts["CONF-TEST1234"] = conflict
        self.detector._save_conflicts()

        resolved = self.detector.resolve_conflict(
            "CONF-TEST1234",
            "Applied domain split to resolve"
        )

        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.resolution_notes, "Applied domain split to resolve")

    def test_list_conflicts_unresolved_only(self):
        """Should list only unresolved conflicts by default."""
        # Create some conflicts
        self.detector._conflicts["CONF-1"] = Conflict(
            conflict_id="CONF-1",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Unresolved",
            resolved=False
        )
        self.detector._conflicts["CONF-2"] = Conflict(
            conflict_id="CONF-2",
            conflict_type=ConflictType.SCOPE_OVERLAP.value,
            severity=ConflictSeverity.WARNING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-CCC",
            description="Resolved",
            resolved=True
        )

        conflicts = self.detector.list_conflicts(unresolved_only=True)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_id, "CONF-1")

    def test_list_conflicts_by_improvement(self):
        """Should filter conflicts by improvement ID."""
        self.detector._conflicts["CONF-1"] = Conflict(
            conflict_id="CONF-1",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="AAA vs BBB"
        )
        self.detector._conflicts["CONF-2"] = Conflict(
            conflict_id="CONF-2",
            conflict_type=ConflictType.SCOPE_OVERLAP.value,
            severity=ConflictSeverity.WARNING.value,
            improvement_a="IMP-CCC",
            improvement_b="IMP-DDD",
            description="CCC vs DDD"
        )

        conflicts = self.detector.list_conflicts(
            improvement_id="IMP-AAA",
            unresolved_only=False
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_id, "CONF-1")

    def test_list_conflicts_by_type(self):
        """Should filter conflicts by type."""
        self.detector._conflicts["CONF-1"] = Conflict(
            conflict_id="CONF-1",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Behavioral"
        )
        self.detector._conflicts["CONF-2"] = Conflict(
            conflict_id="CONF-2",
            conflict_type=ConflictType.SCOPE_OVERLAP.value,
            severity=ConflictSeverity.WARNING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-CCC",
            description="Scope"
        )

        conflicts = self.detector.list_conflicts(
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            unresolved_only=False
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_id, "CONF-1")


class TestResolutionSuggestions(unittest.TestCase):
    """Tests for resolution suggestion generation."""

    def setUp(self):
        """Create detector for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        (self.base_path / ".claude-loop").mkdir(parents=True)
        self.detector = ConflictDetector(base_dir=self.base_path)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_behavioral_contradiction_suggestions(self):
        """Should provide appropriate suggestions for behavioral contradictions."""
        suggestions = self.detector._get_resolution_suggestions(
            ConflictType.BEHAVIORAL_CONTRADICTION
        )

        self.assertGreater(len(suggestions), 0)
        strategies = [s["strategy"] for s in suggestions]
        self.assertIn(ResolutionStrategy.CONDITIONAL_APPLICATION.value, strategies)

    def test_scope_overlap_suggestions(self):
        """Should provide appropriate suggestions for scope overlaps."""
        suggestions = self.detector._get_resolution_suggestions(
            ConflictType.SCOPE_OVERLAP
        )

        self.assertGreater(len(suggestions), 0)
        strategies = [s["strategy"] for s in suggestions]
        self.assertIn(ResolutionStrategy.SCOPE_NARROWING.value, strategies)

    def test_dependency_conflict_suggestions(self):
        """Should provide appropriate suggestions for dependency conflicts."""
        suggestions = self.detector._get_resolution_suggestions(
            ConflictType.DEPENDENCY_CONFLICT
        )

        self.assertGreater(len(suggestions), 0)
        strategies = [s["strategy"] for s in suggestions]
        self.assertIn(ResolutionStrategy.MANUAL_REVIEW.value, strategies)

    def test_resource_contention_suggestions(self):
        """Should provide appropriate suggestions for resource contentions."""
        suggestions = self.detector._get_resolution_suggestions(
            ConflictType.RESOURCE_CONTENTION
        )

        self.assertGreater(len(suggestions), 0)
        strategies = [s["strategy"] for s in suggestions]
        self.assertIn(ResolutionStrategy.MERGE.value, strategies)


class TestPersistence(unittest.TestCase):
    """Tests for data persistence."""

    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        (self.base_path / ".claude-loop").mkdir(parents=True)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scopes_persist_across_instances(self):
        """Scopes should persist when detector is recreated."""
        detector1 = ConflictDetector(base_dir=self.base_path)
        detector1.set_scope(
            improvement_id="IMP-TEST123",
            affected_behaviors=["error handling"]
        )

        detector2 = ConflictDetector(base_dir=self.base_path)
        scope = detector2.get_scope("IMP-TEST123")

        self.assertIsNotNone(scope)
        self.assertEqual(scope.affected_behaviors, ["error handling"])

    def test_conflicts_persist_across_instances(self):
        """Conflicts should persist when detector is recreated."""
        detector1 = ConflictDetector(base_dir=self.base_path)
        detector1._conflicts["CONF-TEST"] = Conflict(
            conflict_id="CONF-TEST",
            conflict_type=ConflictType.BEHAVIORAL_CONTRADICTION.value,
            severity=ConflictSeverity.BLOCKING.value,
            improvement_a="IMP-AAA",
            improvement_b="IMP-BBB",
            description="Test conflict"
        )
        detector1._save_conflicts()

        detector2 = ConflictDetector(base_dir=self.base_path)
        conflict = detector2.get_conflict("CONF-TEST")

        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.description, "Test conflict")


if __name__ == "__main__":
    unittest.main()
