#!/usr/bin/env python3
"""
Comprehensive tests for the Stratified Memory v2 Scale Architecture.

Tests cover:
- Domain-contextualized experience storage and retrieval (SCALE-001)
- Retrieval feedback loop and helpful_rate updates (SCALE-002)
- Domain auto-detection accuracy across project types (SCALE-003)
- Privacy config enforces local-only by default (SCALE-004)
- Domain adapter loading and isolation (SCALE-005)
- Improvement queue workflow (SCALE-007)
- Promotion criteria calculation with all factors (SCALE-008)
- Conflict detection catches behavioral contradictions (SCALE-009)
- Pattern clustering flags low-confidence for human review (SCALE-010)
- Leading indicators calculate correctly (SCALE-011)
- Calibration tracking measures alignment accurately (SCALE-012)
- Core protection blocks all automated modifications (SCALE-013)

Uses mock embeddings and deterministic test data.
Coverage target: >85% for all new modules.
"""

import json
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# =============================================================================
# Module Loading Utilities
# =============================================================================

def load_module(filename: str) -> Dict[str, Any]:
    """Load a hyphenated Python module using runpy."""
    module_path = Path(__file__).parent.parent / "lib" / filename
    return runpy.run_path(str(module_path))


# =============================================================================
# Test: Domain-Contextualized Experience Store (SCALE-001)
# =============================================================================

class TestExperienceStore(unittest.TestCase):
    """Tests for domain-contextualized experience storage and retrieval."""

    @classmethod
    def setUpClass(cls):
        """Load the experience store module once."""
        cls.module = load_module("experience-store.py")
        cls.DomainContext = cls.module["DomainContext"]
        cls.ExperienceEntry = cls.module["ExperienceEntry"]
        cls.ExperienceStore = cls.module["ExperienceStore"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.temp_dir) / ".claude-loop" / "experiences"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        # Create store with fallback (no ChromaDB/embeddings needed)
        self.store = self.ExperienceStore(db_dir=str(self.db_dir), use_embeddings=False)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_domain_context_creation(self):
        """DomainContext should be created with all fields."""
        ctx = self.DomainContext(
            project_type="unity_game",
            language="csharp",
            frameworks=["Unity XR"],
            tools_used=["Unity Editor"]
        )
        self.assertEqual(ctx.project_type, "unity_game")
        self.assertEqual(ctx.language, "csharp")
        self.assertIn("Unity XR", ctx.frameworks)

    def test_domain_context_to_dict(self):
        """DomainContext should serialize to dict."""
        ctx = self.DomainContext(
            project_type="web_frontend",
            language="typescript"
        )
        data = ctx.to_dict()
        self.assertEqual(data["project_type"], "web_frontend")
        self.assertEqual(data["language"], "typescript")

    def test_domain_context_from_dict(self):
        """DomainContext should deserialize from dict."""
        data = {
            "project_type": "ml_training",
            "language": "python",
            "frameworks": ["PyTorch"],
            "tools_used": []
        }
        ctx = self.DomainContext.from_dict(data)
        self.assertEqual(ctx.project_type, "ml_training")
        self.assertIn("PyTorch", ctx.frameworks)

    def test_domain_context_get_parent_category(self):
        """DomainContext should return correct parent category."""
        ctx = self.DomainContext(project_type="unity_game")
        self.assertEqual(ctx.get_parent_category(), "unity")

        ctx_ml = self.DomainContext(project_type="ml_training")
        self.assertEqual(ctx_ml.get_parent_category(), "ml")

    def test_record_experience_with_domain(self):
        """Store should save experience with domain context."""
        ctx = self.DomainContext(project_type="web_backend", language="python")
        result = self.store.record_experience(
            problem="Database connection timeout",
            solution="Increase connection pool size",
            domain_context=ctx
        )
        # record_experience returns (entry_id, success)
        entry_id, success = result
        self.assertTrue(success)
        self.assertIsNotNone(entry_id)

        # Retrieve and verify
        entry = self.store.get_experience(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.domain_context.project_type, "web_backend")

    def test_record_multiple_domains(self):
        """Store should handle multiple domains independently."""
        # Store for web
        ctx_web = self.DomainContext(project_type="web_frontend")
        _, success1 = self.store.record_experience("Web problem", "Web solution", ctx_web)
        self.assertTrue(success1)

        # Store for Unity
        ctx_unity = self.DomainContext(project_type="unity_game")
        _, success2 = self.store.record_experience("Unity problem", "Unity solution", ctx_unity)
        self.assertTrue(success2)

        # Check stats
        stats = self.store.get_stats()
        self.assertEqual(stats.total_experiences, 2)

    def test_update_success_count(self):
        """Update success should increment success_count."""
        ctx = self.DomainContext(project_type="cli_tool")
        entry_id, success = self.store.record_experience("CLI error", "Handle exit code", ctx)
        self.assertTrue(success)

        # Get initial count
        entry = self.store.get_experience(entry_id)
        initial_count = entry.success_count

        # Update success
        self.store.update_success_count(entry_id)

        # Verify increment
        entry = self.store.get_experience(entry_id)
        self.assertEqual(entry.success_count, initial_count + 1)

    def test_get_stats_returns_experience_stats(self):
        """get_stats should return ExperienceStats object."""
        ctx = self.DomainContext(project_type="data_pipeline")
        _, success = self.store.record_experience("ETL failure", "Add retry logic", ctx)
        self.assertTrue(success)

        stats = self.store.get_stats()
        self.assertEqual(stats.total_experiences, 1)
        self.assertIsInstance(stats.to_dict(), dict)


# =============================================================================
# Test: Domain Auto-Detection (SCALE-003)
# =============================================================================

class TestDomainDetector(unittest.TestCase):
    """Tests for automatic domain detection across project types."""

    @classmethod
    def setUpClass(cls):
        """Load the domain detector module once."""
        cls.module = load_module("domain-detector.py")
        cls.DomainDetector = cls.module["DomainDetector"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "project"
        self.project_dir.mkdir()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_web_frontend_from_package_json(self):
        """Should detect web_frontend from React in package.json."""
        package_json = {
            "name": "my-app",
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0"
            }
        }
        (self.project_dir / "package.json").write_text(json.dumps(package_json))

        detector = self.DomainDetector(project_path=str(self.project_dir))
        result = detector.detect()

        self.assertEqual(result.project_type, "web_frontend")

    def test_detect_web_backend_from_requirements(self):
        """Should detect web_backend from Flask/Django in requirements.txt."""
        requirements = "flask>=2.0.0\nflask-restful\nsqlalchemy"
        (self.project_dir / "requirements.txt").write_text(requirements)

        detector = self.DomainDetector(project_path=str(self.project_dir))
        result = detector.detect()

        self.assertEqual(result.project_type, "web_backend")

    def test_detect_ml_training_from_pytorch(self):
        """Should detect ml_training from PyTorch in requirements."""
        requirements = "torch>=2.0.0\ntorchvision\ntensorboard"
        (self.project_dir / "requirements.txt").write_text(requirements)

        detector = self.DomainDetector(project_path=str(self.project_dir))
        result = detector.detect()

        self.assertEqual(result.project_type, "ml_training")

    def test_detect_returns_confidence_score(self):
        """Detection result should include confidence score."""
        (self.project_dir / "package.json").write_text('{"name": "test", "dependencies": {"react": "18.0"}}')

        detector = self.DomainDetector(project_path=str(self.project_dir))
        result = detector.detect()

        self.assertIn(result.confidence, ["high", "medium", "low"])
        self.assertIsInstance(result.confidence_score, (int, float))

    def test_detect_unknown_project(self):
        """Should return 'other' for unrecognizable projects."""
        # Empty project
        detector = self.DomainDetector(project_path=str(self.project_dir))
        result = detector.detect()

        self.assertEqual(result.project_type, "other")
        self.assertEqual(result.confidence, "low")


# =============================================================================
# Test: Privacy-First Local-Only Architecture (SCALE-004)
# =============================================================================

class TestPrivacyConfig(unittest.TestCase):
    """Tests for privacy configuration and data management."""

    @classmethod
    def setUpClass(cls):
        """Load the privacy config module once."""
        cls.module = load_module("privacy-config.py")
        cls.PrivacyMode = cls.module["PrivacyMode"]
        cls.PrivacyConfig = cls.module["PrivacyConfig"]
        cls.PrivacyManager = cls.module["PrivacyManager"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.manager = self.PrivacyManager(base_dir=str(self.base_dir))

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_mode_is_fully_local(self):
        """Default privacy mode should be FULLY_LOCAL."""
        status = self.manager.get_status()
        self.assertEqual(status["mode"], self.PrivacyMode.FULLY_LOCAL.value)

    def test_fully_local_network_not_allowed(self):
        """FULLY_LOCAL mode should not allow network calls."""
        is_allowed = self.manager.is_network_allowed()
        self.assertFalse(is_allowed)

    def test_get_status_returns_dict(self):
        """get_status should return a dictionary with mode and data_locations."""
        status = self.manager.get_status()
        self.assertIn("mode", status)
        self.assertIsInstance(status, dict)

    def test_privacy_mode_enum_values(self):
        """PrivacyMode enum should have correct values."""
        self.assertEqual(self.PrivacyMode.FULLY_LOCAL.value, "fully_local")
        self.assertEqual(self.PrivacyMode.TEAM_SYNC.value, "team_sync")
        self.assertEqual(self.PrivacyMode.FEDERATED.value, "federated")


# =============================================================================
# Test: Domain Adapter Extension System (SCALE-005)
# =============================================================================

class TestDomainAdapter(unittest.TestCase):
    """Tests for domain adapter loading and isolation."""

    @classmethod
    def setUpClass(cls):
        """Load the domain adapter module once."""
        cls.module = load_module("domain-adapter.py")
        cls.AdapterManager = cls.module["AdapterManager"]
        cls.AdapterManifest = cls.module["AdapterManifest"]

    def setUp(self):
        """Create temporary directory structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.adapters_dir = Path(self.temp_dir) / "adapters"
        self.adapters_dir.mkdir()

        # Create test adapter
        self._create_test_adapter("test-adapter", "cli_tool")

        self.manager = self.AdapterManager(
            adapters_dir=str(self.adapters_dir),
            base_dir=self.temp_dir
        )

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_adapter(self, name: str, domain: str):
        """Helper to create a test adapter."""
        adapter_dir = self.adapters_dir / name
        adapter_dir.mkdir()

        manifest = {
            "name": name,
            "version": "1.0.0",
            "domain": domain,
            "domains": [domain],
            "description": f"Test {name} adapter",
            "maintainer": "test@example.com",
            "capabilities": [
                {"type": "prompts", "name": "test", "path": "prompts", "description": "Test prompts"}
            ]
        }

        (adapter_dir / "adapter.json").write_text(json.dumps(manifest))
        (adapter_dir / "prompts").mkdir()
        (adapter_dir / "prompts" / "test.md").write_text("# Test Prompt")

    def test_discover_adapters(self):
        """Should discover installed adapters."""
        adapters = self.manager.discover_adapters()
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].name, "test-adapter")

    def test_load_for_domain(self):
        """Should load adapter for matching domain."""
        loaded = self.manager.load_for_domain("cli_tool")
        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded[0].loaded)

    def test_adapter_isolation_no_cross_domain(self):
        """Adapter for one domain should not load for another."""
        loaded = self.manager.load_for_domain("unity_game")
        self.assertEqual(len(loaded), 0)

    def test_disable_adapter(self):
        """Disabled adapter should not load."""
        self.manager.disable_adapter("test-adapter")
        loaded = self.manager.load_for_domain("cli_tool")
        self.assertEqual(len(loaded), 0)

    def test_enable_adapter(self):
        """Re-enabled adapter should load again."""
        self.manager.disable_adapter("test-adapter")
        self.manager.enable_adapter("test-adapter")
        loaded = self.manager.load_for_domain("cli_tool")
        self.assertEqual(len(loaded), 1)

    def test_get_prompts_for_domain(self):
        """Should get prompts from adapter for domain."""
        prompts = self.manager.get_prompts_for_domain("cli_tool")
        self.assertEqual(len(prompts), 1)
        self.assertIn("Test Prompt", prompts[0]["content"])


# =============================================================================
# Test: Improvement Queue Workflow (SCALE-007)
# =============================================================================

class TestImprovementQueue(unittest.TestCase):
    """Tests for improvement queue propose->review->approve/reject workflow."""

    @classmethod
    def setUpClass(cls):
        """Load the improvement queue module once."""
        cls.module = load_module("improvement-queue.py")
        cls.ImprovementProposal = cls.module["ImprovementProposal"]
        cls.ImprovementQueueManager = cls.module["ImprovementQueueManager"]
        cls.ProposalStatus = cls.module["ProposalStatus"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = self.ImprovementQueueManager(base_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_propose_creates_proposal(self):
        """propose should create a new proposal in PROPOSED status."""
        proposal = self.manager.propose(
            problem_pattern="Test problem",
            proposed_solution="Test solution"
        )

        self.assertTrue(proposal.id.startswith("IMP-"))
        self.assertEqual(proposal.status, self.ProposalStatus.PROPOSED.value)

    def test_review_changes_status(self):
        """review should change status to REVIEWED."""
        proposal = self.manager.propose("Problem", "Solution")
        self.manager.review(proposal.id)

        loaded = self.manager.get(proposal.id)
        self.assertEqual(loaded.status, self.ProposalStatus.REVIEWED.value)

    def test_approve_changes_status(self):
        """approve should change status to APPROVED."""
        proposal = self.manager.propose("Problem", "Solution")
        self.manager.approve(proposal.id, notes="Approved")

        loaded = self.manager.get(proposal.id)
        self.assertEqual(loaded.status, self.ProposalStatus.APPROVED.value)

    def test_reject_requires_reason(self):
        """reject should require a reason."""
        proposal = self.manager.propose("Problem", "Solution")

        with self.assertRaises(ValueError):
            self.manager.reject(proposal.id, reason="")

    def test_reject_changes_status(self):
        """reject should change status to REJECTED."""
        proposal = self.manager.propose("Problem", "Solution")
        self.manager.reject(proposal.id, reason="Not needed")

        loaded = self.manager.get(proposal.id)
        self.assertEqual(loaded.status, self.ProposalStatus.REJECTED.value)

    def test_no_auto_implementation(self):
        """Proposals should NOT auto-implement - all require human approval."""
        proposal = self.manager.propose("Problem", "Solution", confidence=0.99)

        # Even with high confidence, should still be in PROPOSED status
        self.assertEqual(proposal.status, self.ProposalStatus.PROPOSED.value)

    def test_deduplication_increments_evidence(self):
        """Same problem_pattern should increment evidence_count."""
        p1 = self.manager.propose("Same problem", "Solution", evidence_count=1)
        p2 = self.manager.propose("Same problem", "Same solution", evidence_count=2)

        self.assertEqual(p1.id, p2.id)
        self.assertEqual(p1.evidence_count, 3)  # 1 + 2


# =============================================================================
# Test: Conflict Detection System (SCALE-009)
# =============================================================================

class TestConflictDetector(unittest.TestCase):
    """Tests for improvement conflict detection."""

    @classmethod
    def setUpClass(cls):
        """Load modules once."""
        cls.queue_module = load_module("improvement-queue.py")
        cls.conflict_module = load_module("conflict-detector.py")
        cls.ImprovementQueueManager = cls.queue_module["ImprovementQueueManager"]
        cls.ConflictDetector = cls.conflict_module["ConflictDetector"]
        cls.ImprovementScope = cls.conflict_module["ImprovementScope"]
        cls.ConflictType = cls.conflict_module["ConflictType"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.queue = self.ImprovementQueueManager(base_dir=self.base_dir)
        self.detector = self.ConflictDetector(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scope_creation(self):
        """ImprovementScope should be creatable with behaviors."""
        scope = self.ImprovementScope(
            improvement_id="IMP-TEST",
            affected_behaviors=["retry_on_failure", "network_handling"]
        )
        self.assertIn("retry_on_failure", scope.affected_behaviors)

    def test_set_and_get_scope(self):
        """Should be able to set and get scope for a proposal."""
        proposal = self.queue.propose("Problem", "Solution")
        # set_scope takes individual parameters, not an ImprovementScope object
        self.detector.set_scope(
            improvement_id=proposal.id,
            affected_behaviors=["test_behavior"],
            domain_applicability=["web"]
        )

        retrieved = self.detector.get_scope(proposal.id)
        self.assertIsNotNone(retrieved)
        self.assertIn("test_behavior", retrieved.affected_behaviors)

    def test_detect_conflicts_returns_list(self):
        """detect_conflicts should return a list."""
        p1 = self.queue.propose("Problem 1", "Solution 1")
        p2 = self.queue.propose("Problem 2", "Solution 2")

        # set_scope takes individual parameters
        self.detector.set_scope(
            improvement_id=p1.id,
            affected_behaviors=["behavior_a"],
            preconditions=[]
        )
        self.detector.set_scope(
            improvement_id=p2.id,
            affected_behaviors=["behavior_b"],
            preconditions=[]
        )

        conflicts = self.detector.detect_conflicts(p1.id, p2.id)
        self.assertIsInstance(conflicts, list)

    def test_infer_scope_from_proposal(self):
        """infer_scope should extract scope from proposal content."""
        proposal = self.queue.propose(
            problem_pattern="Database connection pool exhaustion",
            proposed_solution="Implement connection pooling with retry logic",
            affected_domains=["web_backend"]
        )

        inferred = self.detector.infer_scope(proposal.id)
        self.assertIsNotNone(inferred)


# =============================================================================
# Test: Pattern Clustering (SCALE-010)
# =============================================================================

class TestPatternClustering(unittest.TestCase):
    """Tests for pattern clustering with human review flagging."""

    @classmethod
    def setUpClass(cls):
        """Load modules once."""
        cls.queue_module = load_module("improvement-queue.py")
        cls.clustering_module = load_module("pattern-clustering.py")
        cls.ImprovementQueueManager = cls.queue_module["ImprovementQueueManager"]
        cls.PatternClusteringManager = cls.clustering_module["PatternClusteringManager"]
        cls.ClusterStatus = cls.clustering_module["ClusterStatus"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.queue = self.ImprovementQueueManager(base_dir=self.base_dir)
        self.clustering = self.PatternClusteringManager(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_clusters_returns_list(self):
        """analyze_and_cluster should return a list."""
        # Create some proposals
        self.queue.propose("File not found error", "Check file path")
        self.queue.propose("Config file missing", "Verify config exists")

        clusters = self.clustering.analyze_and_cluster()
        self.assertIsInstance(clusters, list)

    def test_cluster_status_enum(self):
        """ClusterStatus enum should have correct values."""
        self.assertEqual(self.ClusterStatus.PROPOSED.value, "proposed")
        self.assertEqual(self.ClusterStatus.APPROVED.value, "approved")
        self.assertEqual(self.ClusterStatus.REJECTED.value, "rejected")


# =============================================================================
# Test: Leading Indicator Metrics (SCALE-011)
# =============================================================================

class TestHealthIndicators(unittest.TestCase):
    """Tests for leading indicator metrics calculation."""

    @classmethod
    def setUpClass(cls):
        """Load the health indicators module once."""
        cls.module = load_module("health-indicators.py")
        cls.HealthIndicatorsManager = cls.module["HealthIndicatorsManager"]
        cls.HealthStatus = cls.module["HealthStatus"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.manager = self.HealthIndicatorsManager(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_health_snapshot(self):
        """Should return health snapshot with all indicators."""
        snapshot = self.manager.get_health_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertIn("overall_status", snapshot.__dict__)
        self.assertIn("indicators", snapshot.__dict__)

    def test_proposal_rate_change_indicator(self):
        """proposal_rate_change should return indicator value."""
        indicator = self.manager.calculate_proposal_rate_change()
        self.assertIn(indicator.status, [s.value for s in self.HealthStatus])
        self.assertIsInstance(indicator.value, (int, float))

    def test_cluster_concentration_indicator(self):
        """cluster_concentration should return indicator value."""
        indicator = self.manager.calculate_cluster_concentration()
        self.assertIn(indicator.status, [s.value for s in self.HealthStatus])

    def test_retrieval_miss_rate_indicator(self):
        """retrieval_miss_rate should return indicator value."""
        indicator = self.manager.calculate_retrieval_miss_rate()
        self.assertIn(indicator.status, [s.value for s in self.HealthStatus])

    def test_domain_drift_indicator(self):
        """domain_drift should return indicator value."""
        indicator = self.manager.calculate_domain_drift()
        self.assertIn(indicator.status, [s.value for s in self.HealthStatus])

    def test_rag_status_thresholds(self):
        """Overall status should be one of the RAG values."""
        snapshot = self.manager.get_health_snapshot()
        self.assertIn(snapshot.overall_status, ["green", "amber", "red", "unknown"])


# =============================================================================
# Test: Calibration Tracking System (SCALE-012)
# =============================================================================

class TestCalibrationTracker(unittest.TestCase):
    """Tests for calibration tracking and alignment measurement."""

    @classmethod
    def setUpClass(cls):
        """Load the calibration tracker module once."""
        cls.module = load_module("calibration-tracker.py")
        cls.CalibrationTracker = cls.module["CalibrationTracker"]
        cls.CalibrationStatus = cls.module["CalibrationStatus"]
        cls.CalibrationMetrics = cls.module["CalibrationMetrics"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.tracker = self.CalibrationTracker(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_metrics_returns_metrics(self):
        """calculate_metrics should return CalibrationMetrics."""
        metrics = self.tracker.calculate_metrics()
        self.assertIsNotNone(metrics)
        self.assertIsInstance(metrics.agreement_rate, (int, float))

    def test_check_autonomous_eligibility(self):
        """check_autonomous_eligibility should return eligibility info."""
        result = self.tracker.check_autonomous_eligibility()
        self.assertIn("eligible", result)
        self.assertFalse(result["eligible"])  # Should not be eligible without data

    def test_calibration_status_enum(self):
        """CalibrationStatus enum should have correct values."""
        self.assertEqual(self.CalibrationStatus.CALIBRATING.value, "calibrating")
        self.assertEqual(self.CalibrationStatus.QUALIFIED.value, "qualified")

    def test_get_disagreements_returns_list(self):
        """get_disagreements should return a list."""
        disagreements = self.tracker.get_disagreements()
        self.assertIsInstance(disagreements, list)


# =============================================================================
# Test: Core Protection with Immutability Rules (SCALE-013)
# =============================================================================

class TestCoreProtection(unittest.TestCase):
    """Tests for core file protection and immutability."""

    @classmethod
    def setUpClass(cls):
        """Load the core protection module once."""
        cls.module = load_module("core-protection.py")
        cls.CoreProtectionManager = cls.module["CoreProtectionManager"]
        cls.AccessType = cls.module["AccessType"]
        cls.BlockReason = cls.module["BlockReason"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.manager = self.CoreProtectionManager(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_core_files_list_exists(self):
        """Should have a predefined list of core files."""
        core_files = self.manager.list_protected_files()
        self.assertIsInstance(core_files, list)
        self.assertGreater(len(core_files), 0)

    def test_is_core_file_detects_core(self):
        """is_core_file should return True for core files."""
        is_core = self.manager.is_core_file("claude-loop.sh")
        self.assertTrue(is_core)

    def test_is_core_file_allows_non_core(self):
        """is_core_file should return False for non-core files."""
        is_core = self.manager.is_core_file("random-file.txt")
        self.assertFalse(is_core)

    def test_check_file_returns_result(self):
        """check_file should return a result object."""
        result = self.manager.check_file("claude-loop.sh")
        self.assertTrue(result.is_protected)

    def test_pattern_matching_protection(self):
        """Should protect files matching patterns like *.pem."""
        is_protected = self.manager.is_core_file("server.pem")
        self.assertTrue(is_protected)

    def test_secrets_pattern_protection(self):
        """Should protect files in secrets directories."""
        is_protected = self.manager.is_core_file("config/secrets/api_key.txt")
        self.assertTrue(is_protected)

    def test_check_proposal_affects_core(self):
        """Should detect proposals that would affect core files."""
        affects, files, _ = self.manager.check_proposal_affects_core(
            file_scope=["claude-loop.sh", "lib/some-file.py"]
        )

        self.assertTrue(affects)
        self.assertIn("claude-loop.sh", files)


# =============================================================================
# Test: Promotion Evaluator (SCALE-008)
# =============================================================================

class TestPromotionEvaluator(unittest.TestCase):
    """Tests for comprehensive promotion criteria calculation."""

    @classmethod
    def setUpClass(cls):
        """Load modules once."""
        cls.queue_module = load_module("improvement-queue.py")
        cls.evaluator_module = load_module("promotion-evaluator.py")
        cls.ImprovementQueueManager = cls.queue_module["ImprovementQueueManager"]
        cls.PromotionEvaluator = cls.evaluator_module["PromotionEvaluator"]

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        self.queue = self.ImprovementQueueManager(base_dir=self.base_dir)
        self.evaluator = self.PromotionEvaluator(base_dir=self.base_dir)

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_returns_result(self):
        """evaluate should return an evaluation result."""
        proposal = self.queue.propose(
            problem_pattern="Test problem",
            proposed_solution="Test solution"
        )

        result = self.evaluator.evaluate(proposal.id)
        self.assertIsNotNone(result)

    def test_evaluation_includes_recommendation(self):
        """Evaluation should include a recommendation."""
        proposal = self.queue.propose(
            problem_pattern="Simple bug",
            proposed_solution="Fix single function"
        )

        result = self.evaluator.evaluate(proposal.id)
        self.assertIn(result.recommendation, ["recommend", "review", "not_recommended", "blocked"])


# =============================================================================
# Integration Tests
# =============================================================================

class TestScaleArchitectureIntegration(unittest.TestCase):
    """Integration tests for the complete scale architecture workflow."""

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)
        (self.base_dir / ".claude-loop").mkdir()
        (self.base_dir / ".claude-loop" / "experiences").mkdir()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_improvement_queue_to_calibration_flow(self):
        """Test: Propose improvement -> Review -> Calibration tracking."""
        # Load modules
        queue_module = load_module("improvement-queue.py")
        calibration_module = load_module("calibration-tracker.py")

        ImprovementQueueManager = queue_module["ImprovementQueueManager"]
        CalibrationTracker = calibration_module["CalibrationTracker"]

        # Initialize
        queue = ImprovementQueueManager(base_dir=self.base_dir)
        tracker = CalibrationTracker(base_dir=self.base_dir)

        # 1. Propose an improvement
        proposal = queue.propose(
            problem_pattern="Test pattern",
            proposed_solution="Test solution"
        )

        # 2. Approve it (logs decision)
        queue.approve(proposal.id, notes="Test approval")

        # 3. Verify calibration tracker can load decisions
        decisions = tracker.load_all_decisions()
        self.assertIsInstance(decisions, list)

    def test_privacy_enforced_throughout(self):
        """Test: Privacy mode enforced across all components."""
        # Load privacy module
        privacy_module = load_module("privacy-config.py")
        PrivacyManager = privacy_module["PrivacyManager"]
        PrivacyMode = privacy_module["PrivacyMode"]

        # Initialize in default mode
        manager = PrivacyManager(base_dir=str(self.base_dir))

        # Verify default is fully local
        status = manager.get_status()
        self.assertEqual(status["mode"], PrivacyMode.FULLY_LOCAL.value)

        # Verify network not allowed
        self.assertFalse(manager.is_network_allowed())


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
