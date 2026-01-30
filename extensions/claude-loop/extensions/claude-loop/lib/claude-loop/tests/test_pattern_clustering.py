#!/usr/bin/env python3
"""
Unit tests for lib/pattern-clustering.py

Tests cover:
- ClusterProposal dataclass and lifecycle
- ClusterMember dataclass
- Cluster similarity and grouping
- Human validation workflow (approve/reject)
- Accuracy tracking
- CLI commands
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Import using runpy for hyphenated filename
import runpy
pattern_clustering = runpy.run_path(
    str(Path(__file__).parent.parent / "lib" / "pattern-clustering.py")
)

# Extract classes and functions
ClusterStatus = pattern_clustering["ClusterStatus"]
ClusterDecisionType = pattern_clustering["ClusterDecisionType"]
ClusterMember = pattern_clustering["ClusterMember"]
ClusterProposal = pattern_clustering["ClusterProposal"]
ClusterDecision = pattern_clustering["ClusterDecision"]
PatternClusteringManager = pattern_clustering["PatternClusteringManager"]
HIGH_CONFIDENCE_THRESHOLD = pattern_clustering["HIGH_CONFIDENCE_THRESHOLD"]


class TestClusterMember(unittest.TestCase):
    """Tests for ClusterMember dataclass."""

    def test_create_member(self):
        """Test creating a cluster member."""
        member = ClusterMember(
            proposal_id="IMP-12345678",
            problem_pattern="Error handling in API calls",
            proposed_solution="Add retry logic with exponential backoff",
            similarity_to_centroid=0.85,
            domains=["web_backend", "api"]
        )

        self.assertEqual(member.proposal_id, "IMP-12345678")
        self.assertEqual(member.similarity_to_centroid, 0.85)
        self.assertEqual(len(member.domains), 2)

    def test_member_to_dict(self):
        """Test serialization to dict."""
        member = ClusterMember(
            proposal_id="IMP-TEST",
            problem_pattern="Test problem",
            proposed_solution="Test solution"
        )

        data = member.to_dict()
        self.assertEqual(data["proposal_id"], "IMP-TEST")
        self.assertIn("similarity_to_centroid", data)

    def test_member_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "proposal_id": "IMP-FROMDICT",
            "problem_pattern": "Dict problem",
            "proposed_solution": "Dict solution",
            "similarity_to_centroid": 0.75,
            "domains": ["ml"]
        }

        member = ClusterMember.from_dict(data)
        self.assertEqual(member.proposal_id, "IMP-FROMDICT")
        self.assertEqual(member.similarity_to_centroid, 0.75)


class TestClusterProposal(unittest.TestCase):
    """Tests for ClusterProposal dataclass."""

    def test_create_proposal(self):
        """Test creating a cluster proposal."""
        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Problem 1",
                proposed_solution="Solution 1"
            ),
            ClusterMember(
                proposal_id="IMP-002",
                problem_pattern="Problem 2",
                proposed_solution="Solution 2"
            )
        ]

        cluster = ClusterProposal(
            cluster_id="",
            member_improvements=members,
            proposed_generalization="Common error handling pattern",
            confidence=0.75
        )

        # ID should be auto-generated
        self.assertTrue(cluster.cluster_id.startswith("CLU-"))
        self.assertEqual(len(cluster.member_improvements), 2)
        self.assertEqual(cluster.status, ClusterStatus.PROPOSED.value)

    def test_auto_validation_requirement(self):
        """Test that requires_human_validation is set based on confidence."""
        # Low confidence = requires validation
        low_conf = ClusterProposal(
            cluster_id="",
            confidence=0.5
        )
        self.assertTrue(low_conf.requires_human_validation)

        # High confidence = doesn't require validation
        high_conf = ClusterProposal(
            cluster_id="",
            confidence=0.9
        )
        self.assertFalse(high_conf.requires_human_validation)

        # At threshold = doesn't require validation
        at_threshold = ClusterProposal(
            cluster_id="",
            confidence=HIGH_CONFIDENCE_THRESHOLD
        )
        self.assertFalse(at_threshold.requires_human_validation)

    def test_is_actionable(self):
        """Test is_actionable returns correct value based on status."""
        cluster = ClusterProposal(cluster_id="", confidence=0.5)

        # Proposed = actionable
        self.assertTrue(cluster.is_actionable())

        # Approved = not actionable
        cluster.status = ClusterStatus.APPROVED.value
        self.assertFalse(cluster.is_actionable())

        # Rejected = not actionable
        cluster.status = ClusterStatus.REJECTED.value
        self.assertFalse(cluster.is_actionable())

    def test_to_dict_from_dict(self):
        """Test serialization roundtrip."""
        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Problem 1",
                proposed_solution="Solution 1"
            )
        ]

        original = ClusterProposal(
            cluster_id="CLU-TEST1234",
            member_improvements=members,
            proposed_generalization="Test generalization",
            confidence=0.72,
            domain_coverage=["web", "api"]
        )

        data = original.to_dict()
        restored = ClusterProposal.from_dict(data)

        self.assertEqual(restored.cluster_id, original.cluster_id)
        self.assertEqual(restored.confidence, original.confidence)
        self.assertEqual(len(restored.member_improvements), 1)


class TestClusterDecision(unittest.TestCase):
    """Tests for ClusterDecision dataclass."""

    def test_create_decision(self):
        """Test creating a cluster decision."""
        decision = ClusterDecision(
            cluster_id="CLU-12345678",
            decision_type=ClusterDecisionType.APPROVE.value,
            system_confidence=0.85,
            human_decision="approve",
            reasoning="Good cluster"
        )

        self.assertEqual(decision.cluster_id, "CLU-12345678")
        self.assertTrue(decision.timestamp)  # Auto-generated

    def test_agreement_calculation_high_confidence(self):
        """Test agreement calculation for high confidence clusters."""
        # High confidence + approve = agreement
        approve = ClusterDecision(
            cluster_id="CLU-TEST",
            decision_type=ClusterDecisionType.APPROVE.value,
            system_confidence=0.9
        )
        self.assertTrue(approve.agreement)

        # High confidence + reject = disagreement
        reject = ClusterDecision(
            cluster_id="CLU-TEST",
            decision_type=ClusterDecisionType.REJECT.value,
            system_confidence=0.9
        )
        self.assertFalse(reject.agreement)

    def test_agreement_calculation_low_confidence(self):
        """Test agreement calculation for low confidence clusters."""
        # Low confidence + reject = agreement (expected behavior)
        reject = ClusterDecision(
            cluster_id="CLU-TEST",
            decision_type=ClusterDecisionType.REJECT.value,
            system_confidence=0.5
        )
        self.assertTrue(reject.agreement)

        # Low confidence + approve = disagreement
        approve = ClusterDecision(
            cluster_id="CLU-TEST",
            decision_type=ClusterDecisionType.APPROVE.value,
            system_confidence=0.5
        )
        self.assertFalse(approve.agreement)


class TestPatternClusteringManager(unittest.TestCase):
    """Tests for PatternClusteringManager class."""

    def setUp(self):
        """Set up test directory and manager."""
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir)

        # Create .claude-loop directory
        (self.base_path / ".claude-loop").mkdir(parents=True, exist_ok=True)

        self.manager = PatternClusteringManager(base_dir=self.base_path)

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)

    def _create_test_queue(self, proposals: list[dict]) -> None:
        """Helper to create a test improvement queue."""
        queue_file = self.base_path / ".claude-loop" / "improvement_queue.json"
        queue_data = {
            "version": "1.0",
            "proposals": {p["id"]: p for p in proposals}
        }
        queue_file.write_text(json.dumps(queue_data))

    def _create_test_cluster(
        self,
        cluster_id: str = "CLU-TEST1234",
        confidence: float = 0.75,
        status: str = ClusterStatus.PROPOSED.value
    ) -> ClusterProposal:
        """Helper to create a test cluster."""
        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Problem 1",
                proposed_solution="Solution 1"
            ),
            ClusterMember(
                proposal_id="IMP-002",
                problem_pattern="Problem 2",
                proposed_solution="Solution 2"
            )
        ]

        cluster = ClusterProposal(
            cluster_id=cluster_id,
            member_improvements=members,
            proposed_generalization="Test generalization",
            confidence=confidence,
            status=status
        )

        self.manager._clusters[cluster.cluster_id] = cluster
        self.manager._save_clusters()
        return cluster

    def test_get_cluster(self):
        """Test getting a cluster by ID."""
        cluster = self._create_test_cluster()

        retrieved = self.manager.get(cluster.cluster_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.cluster_id, cluster.cluster_id)

        # Non-existent cluster
        self.assertIsNone(self.manager.get("CLU-NONEXISTENT"))

    def test_list_clusters(self):
        """Test listing clusters with filters."""
        self._create_test_cluster("CLU-001", confidence=0.5, status=ClusterStatus.PROPOSED.value)
        self._create_test_cluster("CLU-002", confidence=0.9, status=ClusterStatus.PROPOSED.value)
        self._create_test_cluster("CLU-003", confidence=0.7, status=ClusterStatus.APPROVED.value)

        # All clusters
        all_clusters = self.manager.list_clusters()
        self.assertEqual(len(all_clusters), 3)

        # Filter by status
        proposed = self.manager.list_clusters(status=ClusterStatus.PROPOSED.value)
        self.assertEqual(len(proposed), 2)

        approved = self.manager.list_clusters(status=ClusterStatus.APPROVED.value)
        self.assertEqual(len(approved), 1)

    def test_list_requiring_validation(self):
        """Test listing clusters requiring human validation."""
        self._create_test_cluster("CLU-LOW", confidence=0.5)  # Requires validation
        self._create_test_cluster("CLU-HIGH", confidence=0.9)  # Doesn't require

        requiring = self.manager.list_requiring_validation()
        self.assertEqual(len(requiring), 1)
        self.assertEqual(requiring[0].cluster_id, "CLU-LOW")

    def test_approve_cluster(self):
        """Test approving a cluster."""
        cluster = self._create_test_cluster()

        approved = self.manager.approve(
            cluster.cluster_id,
            generalization="Approved error handling pattern",
            notes="Good cluster"
        )

        self.assertIsNotNone(approved)
        self.assertEqual(approved.status, ClusterStatus.APPROVED.value)
        self.assertEqual(approved.approved_generalization, "Approved error handling pattern")
        self.assertTrue(approved.reviewed_at)

    def test_approve_requires_generalization(self):
        """Test that approval requires generalization text."""
        cluster = self._create_test_cluster()

        with self.assertRaises(ValueError):
            self.manager.approve(cluster.cluster_id, generalization="")

    def test_approve_non_actionable(self):
        """Test that already approved cluster cannot be approved again."""
        cluster = self._create_test_cluster(status=ClusterStatus.APPROVED.value)

        result = self.manager.approve(cluster.cluster_id, generalization="Test")
        self.assertIsNone(result)

    def test_reject_cluster(self):
        """Test rejecting a cluster."""
        cluster = self._create_test_cluster()

        rejected = self.manager.reject(
            cluster.cluster_id,
            reason="Members are not related"
        )

        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.status, ClusterStatus.REJECTED.value)
        self.assertEqual(rejected.reviewer_notes, "Members are not related")

    def test_reject_requires_reason(self):
        """Test that rejection requires a reason."""
        cluster = self._create_test_cluster()

        with self.assertRaises(ValueError):
            self.manager.reject(cluster.cluster_id, reason="")

    def test_mark_merged(self):
        """Test marking an approved cluster as merged."""
        cluster = self._create_test_cluster(status=ClusterStatus.APPROVED.value)

        merged = self.manager.mark_merged(cluster.cluster_id, "IMP-MERGED")
        self.assertIsNotNone(merged)
        self.assertEqual(merged.status, ClusterStatus.MERGED.value)
        self.assertIn("Merged to: IMP-MERGED", merged.reviewer_notes)

    def test_mark_merged_requires_approved(self):
        """Test that only approved clusters can be merged."""
        cluster = self._create_test_cluster(status=ClusterStatus.PROPOSED.value)

        result = self.manager.mark_merged(cluster.cluster_id)
        self.assertIsNone(result)

    def test_decision_logging(self):
        """Test that decisions are logged for accuracy tracking."""
        cluster = self._create_test_cluster()

        self.manager.approve(
            cluster.cluster_id,
            generalization="Test generalization",
            notes="Test notes"
        )

        # Check decisions file exists
        decisions_file = self.base_path / ".claude-loop" / "cluster_decisions.jsonl"
        self.assertTrue(decisions_file.exists())

        # Parse decision
        lines = decisions_file.read_text().splitlines()
        self.assertEqual(len(lines), 1)

        decision = json.loads(lines[0])
        self.assertEqual(decision["cluster_id"], cluster.cluster_id)
        self.assertEqual(decision["decision_type"], "approve")

    def test_get_accuracy_metrics_empty(self):
        """Test accuracy metrics with no decisions."""
        metrics = self.manager.get_accuracy_metrics()

        self.assertEqual(metrics["total_decisions"], 0)
        self.assertEqual(metrics["agreement_rate"], 0.0)

    def test_get_accuracy_metrics_with_decisions(self):
        """Test accuracy metrics with decisions."""
        # Create and approve/reject some clusters
        cluster1 = self._create_test_cluster("CLU-001", confidence=0.9)
        cluster2 = self._create_test_cluster("CLU-002", confidence=0.5)

        self.manager.approve(cluster1.cluster_id, generalization="Test 1")
        self.manager.reject(cluster2.cluster_id, reason="Not related")

        metrics = self.manager.get_accuracy_metrics()

        self.assertEqual(metrics["total_decisions"], 2)
        # Both should agree: high conf approved, low conf rejected
        self.assertEqual(metrics["agreement_rate"], 1.0)

    def test_get_statistics(self):
        """Test getting clustering statistics."""
        self._create_test_cluster("CLU-001", confidence=0.5, status=ClusterStatus.PROPOSED.value)
        self._create_test_cluster("CLU-002", confidence=0.9, status=ClusterStatus.APPROVED.value)

        stats = self.manager.get_statistics()

        self.assertEqual(stats["total_clusters"], 2)
        self.assertEqual(stats["pending_count"], 1)
        self.assertEqual(stats["approved_count"], 1)
        self.assertEqual(stats["total_members"], 4)  # 2 members each

    def test_get_weekly_uncertain_clusters(self):
        """Test getting uncertain clusters older than 1 week."""
        # Create a cluster that's old
        self._create_test_cluster("CLU-OLD", confidence=0.5)

        # Manually set created_at to 8 days ago
        old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat().replace("+00:00", "Z")
        self.manager._clusters["CLU-OLD"].created_at = old_date
        self.manager._save_clusters()

        # Create a recent cluster
        self._create_test_cluster("CLU-NEW", confidence=0.5)

        weekly = self.manager.get_weekly_uncertain_clusters()
        self.assertEqual(len(weekly), 1)
        self.assertEqual(weekly[0].cluster_id, "CLU-OLD")

    def test_persistence(self):
        """Test that clusters are persisted and loaded correctly."""
        cluster = self._create_test_cluster()
        cluster_id = cluster.cluster_id

        # Create new manager (simulates restart)
        new_manager = PatternClusteringManager(base_dir=self.base_path)

        loaded = new_manager.get(cluster_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.cluster_id, cluster_id)
        self.assertEqual(loaded.confidence, cluster.confidence)

    def test_compute_similarity_fallback(self):
        """Test text-based similarity fallback when embeddings unavailable."""
        # Test with similar texts
        sim1 = self.manager._compute_similarity(
            "Error handling in API calls",
            "Error handling in API requests"
        )
        self.assertGreater(sim1, 0.5)

        # Test with different texts
        sim2 = self.manager._compute_similarity(
            "Error handling in API calls",
            "User authentication flow"
        )
        self.assertLess(sim2, 0.5)

    def test_generate_generalization(self):
        """Test generalization generation from members."""
        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Error handling in API calls fails silently",
                proposed_solution="Add logging"
            ),
            ClusterMember(
                proposal_id="IMP-002",
                problem_pattern="Error handling in database calls fails",
                proposed_solution="Add retry"
            )
        ]

        gen = self.manager._generate_generalization(members)
        self.assertIn("error", gen.lower())
        self.assertIn("2", gen)  # Should mention 2 improvements

    def test_calculate_cluster_confidence(self):
        """Test cluster confidence calculation."""
        members = [
            ClusterMember(proposal_id="IMP-001", problem_pattern="P1", proposed_solution="S1"),
            ClusterMember(proposal_id="IMP-002", problem_pattern="P2", proposed_solution="S2")
        ]

        # High similarity = high confidence
        high_conf = self.manager._calculate_cluster_confidence(
            members,
            [0.9, 0.9]
        )
        self.assertGreater(high_conf, 0.7)

        # Low similarity = low confidence
        low_conf = self.manager._calculate_cluster_confidence(
            members,
            [0.3, 0.3]
        )
        self.assertLess(low_conf, 0.5)


class TestAnalyzeAndCluster(unittest.TestCase):
    """Tests for the analyze_and_cluster functionality."""

    def setUp(self):
        """Set up test directory and manager."""
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir)
        (self.base_path / ".claude-loop").mkdir(parents=True, exist_ok=True)
        self.manager = PatternClusteringManager(base_dir=self.base_path)

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)

    def _create_test_queue(self, proposals: list[dict]) -> None:
        """Helper to create a test improvement queue."""
        queue_file = self.base_path / ".claude-loop" / "improvement_queue.json"
        queue_data = {
            "version": "1.0",
            "proposals": {p["id"]: p for p in proposals}
        }
        queue_file.write_text(json.dumps(queue_data))

    def test_analyze_empty_queue(self):
        """Test analysis with empty queue."""
        clusters = self.manager.analyze_and_cluster()
        self.assertEqual(len(clusters), 0)

    def test_analyze_insufficient_proposals(self):
        """Test analysis with insufficient proposals."""
        self._create_test_queue([
            {
                "id": "IMP-001",
                "problem_pattern": "Single problem",
                "proposed_solution": "Single solution",
                "status": "proposed"
            }
        ])

        clusters = self.manager.analyze_and_cluster()
        self.assertEqual(len(clusters), 0)

    def test_analyze_similar_proposals(self):
        """Test analysis groups similar proposals."""
        self._create_test_queue([
            {
                "id": "IMP-001",
                "problem_pattern": "Error handling in API calls fails silently",
                "proposed_solution": "Add error logging and retry",
                "status": "proposed",
                "affected_domains": ["web"]
            },
            {
                "id": "IMP-002",
                "problem_pattern": "Error handling in API requests fails",
                "proposed_solution": "Implement error logging",
                "status": "proposed",
                "affected_domains": ["web"]
            },
            {
                "id": "IMP-003",
                "problem_pattern": "User authentication flow is broken",
                "proposed_solution": "Fix token validation",
                "status": "proposed",
                "affected_domains": ["auth"]
            }
        ])

        clusters = self.manager.analyze_and_cluster(
            min_cluster_size=2,
            similarity_threshold=0.5  # Lower threshold for text-based similarity
        )

        # Should create at least one cluster for the similar error handling proposals
        self.assertGreater(len(clusters), 0)

    def test_analyze_respects_status_filter(self):
        """Test that only proposed/reviewed proposals are clustered."""
        self._create_test_queue([
            {
                "id": "IMP-001",
                "problem_pattern": "Problem 1",
                "proposed_solution": "Solution 1",
                "status": "proposed"
            },
            {
                "id": "IMP-002",
                "problem_pattern": "Problem 1 similar",
                "proposed_solution": "Solution 1 similar",
                "status": "approved"  # Should be excluded
            }
        ])

        clusters = self.manager.analyze_and_cluster()
        # Not enough proposals after filtering
        self.assertEqual(len(clusters), 0)


class TestCLI(unittest.TestCase):
    """Tests for CLI interface."""

    def setUp(self):
        """Set up test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir)
        (self.base_path / ".claude-loop").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_create_parser(self):
        """Test parser creation."""
        create_parser = pattern_clustering["create_parser"]
        parser = create_parser()
        self.assertIsNotNone(parser)

    def test_format_cluster(self):
        """Test cluster formatting."""
        format_cluster = pattern_clustering["format_cluster"]

        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Test problem",
                proposed_solution="Test solution",
                similarity_to_centroid=0.85
            )
        ]

        cluster = ClusterProposal(
            cluster_id="CLU-FORMAT",
            member_improvements=members,
            proposed_generalization="Test generalization",
            confidence=0.75,
            domain_coverage=["web"]
        )

        formatted = format_cluster(cluster)
        self.assertIn("CLU-FORMAT", formatted)
        self.assertIn("0.75", formatted)
        self.assertIn("Test generalization", formatted)
        self.assertIn("IMP-001", formatted)

    def test_format_cluster_verbose(self):
        """Test verbose cluster formatting."""
        format_cluster = pattern_clustering["format_cluster"]

        members = [
            ClusterMember(
                proposal_id="IMP-001",
                problem_pattern="Test problem",
                proposed_solution="Test solution"
            )
        ]

        cluster = ClusterProposal(
            cluster_id="CLU-VERBOSE",
            member_improvements=members,
            confidence=0.75,
            centroid_text="Test centroid"
        )

        formatted = format_cluster(cluster, verbose=True)
        self.assertIn("Created:", formatted)
        self.assertIn("Centroid:", formatted)


class TestEnums(unittest.TestCase):
    """Tests for enum classes."""

    def test_cluster_status_values(self):
        """Test ClusterStatus enum values."""
        self.assertEqual(str(ClusterStatus.PROPOSED), "proposed")
        self.assertEqual(str(ClusterStatus.APPROVED), "approved")
        self.assertEqual(str(ClusterStatus.REJECTED), "rejected")
        self.assertEqual(str(ClusterStatus.MERGED), "merged")

    def test_decision_type_values(self):
        """Test ClusterDecisionType enum values."""
        self.assertEqual(str(ClusterDecisionType.APPROVE), "approve")
        self.assertEqual(str(ClusterDecisionType.REJECT), "reject")
        self.assertEqual(str(ClusterDecisionType.SPLIT), "split")
        self.assertEqual(str(ClusterDecisionType.MODIFY), "modify")


if __name__ == "__main__":
    unittest.main()
