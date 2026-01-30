#!/usr/bin/env python3
"""
Tests for lib/improvement-queue.py - Human-Gated Improvement Queue
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Import the module using runpy to handle the hyphenated filename
import runpy
module_path = Path(__file__).parent.parent / "lib" / "improvement-queue.py"
improvement_queue = runpy.run_path(str(module_path))

ImprovementProposal = improvement_queue["ImprovementProposal"]
ReviewerDecision = improvement_queue["ReviewerDecision"]
ImprovementQueueManager = improvement_queue["ImprovementQueueManager"]
ProposalStatus = improvement_queue["ProposalStatus"]
DecisionType = improvement_queue["DecisionType"]


class TestImprovementProposal(unittest.TestCase):
    """Tests for ImprovementProposal dataclass."""

    def test_create_proposal_generates_id(self):
        """Proposal should auto-generate ID if not provided."""
        proposal = ImprovementProposal(
            id="",
            problem_pattern="Test problem",
            proposed_solution="Test solution"
        )
        self.assertTrue(proposal.id.startswith("IMP-"))
        self.assertEqual(len(proposal.id), 12)  # IMP- + 8 hex chars

    def test_create_proposal_calculates_priority(self):
        """Proposal should auto-calculate priority if not provided."""
        proposal = ImprovementProposal(
            id="",
            problem_pattern="Test problem",
            proposed_solution="Test solution",
            confidence=0.8,
            evidence_count=5,
            estimated_impact="high"
        )
        # confidence: 0.8 * 40 = 32
        # evidence: 5/10 * 30 = 15
        # impact (high): 1.0 * 30 = 30
        # total: 77.0
        self.assertEqual(proposal.priority_score, 77.0)

    def test_priority_calculation_medium_impact(self):
        """Priority should use 0.6 multiplier for medium impact."""
        proposal = ImprovementProposal(
            id="",
            problem_pattern="Test problem",
            proposed_solution="Test solution",
            confidence=0.5,
            evidence_count=1,
            estimated_impact="medium"
        )
        # confidence: 0.5 * 40 = 20
        # evidence: 1/10 * 30 = 3
        # impact (medium): 0.6 * 30 = 18
        # total: 41.0
        self.assertEqual(proposal.priority_score, 41.0)

    def test_priority_calculation_low_impact(self):
        """Priority should use 0.3 multiplier for low impact."""
        proposal = ImprovementProposal(
            id="",
            problem_pattern="Test problem",
            proposed_solution="Test solution",
            confidence=0.5,
            evidence_count=1,
            estimated_impact="low"
        )
        # confidence: 0.5 * 40 = 20
        # evidence: 1/10 * 30 = 3
        # impact (low): 0.3 * 30 = 9
        # total: 32.0
        self.assertEqual(proposal.priority_score, 32.0)

    def test_to_dict(self):
        """Proposal should serialize to dict."""
        proposal = ImprovementProposal(
            id="IMP-TEST123",
            problem_pattern="Test problem",
            proposed_solution="Test solution"
        )
        data = proposal.to_dict()
        self.assertEqual(data["id"], "IMP-TEST123")
        self.assertEqual(data["problem_pattern"], "Test problem")
        self.assertIn("created_at", data)

    def test_from_dict(self):
        """Proposal should deserialize from dict."""
        data = {
            "id": "IMP-TEST123",
            "problem_pattern": "Test problem",
            "proposed_solution": "Test solution",
            "status": "approved",
            "priority_score": 50.0
        }
        proposal = ImprovementProposal.from_dict(data)
        self.assertEqual(proposal.id, "IMP-TEST123")
        self.assertEqual(proposal.status, "approved")

    def test_is_actionable(self):
        """is_actionable should return True for proposed/reviewed status."""
        proposal = ImprovementProposal(
            id="IMP-TEST",
            problem_pattern="Test",
            proposed_solution="Test"
        )
        proposal.status = ProposalStatus.PROPOSED.value
        self.assertTrue(proposal.is_actionable())

        proposal.status = ProposalStatus.REVIEWED.value
        self.assertTrue(proposal.is_actionable())

        proposal.status = ProposalStatus.APPROVED.value
        self.assertFalse(proposal.is_actionable())

        proposal.status = ProposalStatus.REJECTED.value
        self.assertFalse(proposal.is_actionable())


class TestReviewerDecision(unittest.TestCase):
    """Tests for ReviewerDecision dataclass."""

    def test_create_decision_generates_timestamp(self):
        """Decision should auto-generate timestamp."""
        decision = ReviewerDecision(
            proposal_id="IMP-TEST",
            decision_type="approve"
        )
        self.assertTrue(decision.timestamp.endswith("Z"))

    def test_agreement_calculated(self):
        """Agreement should be True when system and human match."""
        decision = ReviewerDecision(
            proposal_id="IMP-TEST",
            decision_type="approve",
            system_recommendation="approve",
            human_decision="approve"
        )
        self.assertTrue(decision.agreement)

    def test_disagreement_calculated(self):
        """Agreement should be False when system and human differ."""
        decision = ReviewerDecision(
            proposal_id="IMP-TEST",
            decision_type="approve",
            system_recommendation="review",
            human_decision="approve"
        )
        self.assertFalse(decision.agreement)


class TestImprovementQueueManager(unittest.TestCase):
    """Tests for ImprovementQueueManager class."""

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ImprovementQueueManager(base_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_propose_creates_proposal(self):
        """propose() should create and persist a proposal."""
        proposal = self.manager.propose(
            problem_pattern="File not found",
            proposed_solution="Add validation"
        )
        self.assertTrue(proposal.id.startswith("IMP-"))
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED.value)

        # Should be persisted
        loaded = self.manager.get(proposal.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.problem_pattern, "File not found")

    def test_propose_deduplicates(self):
        """Duplicate problem patterns should increment evidence count."""
        proposal1 = self.manager.propose(
            problem_pattern="Same problem",
            proposed_solution="Solution",
            evidence_count=1
        )
        proposal2 = self.manager.propose(
            problem_pattern="Same problem",
            proposed_solution="Same solution",
            evidence_count=2
        )
        # Should return the same proposal with incremented evidence
        self.assertEqual(proposal1.id, proposal2.id)
        self.assertEqual(proposal1.evidence_count, 3)  # 1 + 2

    def test_list_proposals_filters_by_status(self):
        """list_proposals() should filter by status."""
        self.manager.propose("P1", "S1")
        p2 = self.manager.propose("P2", "S2")
        self.manager.approve(p2.id, notes="OK")

        pending = self.manager.list_proposals(status=ProposalStatus.PROPOSED.value)
        approved = self.manager.list_proposals(status=ProposalStatus.APPROVED.value)

        self.assertEqual(len(pending), 1)
        self.assertEqual(len(approved), 1)

    def test_list_proposals_filters_by_domain(self):
        """list_proposals() should filter by domain."""
        self.manager.propose("P1", "S1", affected_domains=["web"])
        self.manager.propose("P2", "S2", affected_domains=["unity"])

        web_proposals = self.manager.list_proposals(domain="web")
        self.assertEqual(len(web_proposals), 1)

    def test_list_proposals_sorted_by_priority(self):
        """list_proposals() should return sorted by priority descending."""
        self.manager.propose("Low", "S", confidence=0.1, estimated_impact="low")
        self.manager.propose("High", "S", confidence=0.9, estimated_impact="high")
        self.manager.propose("Medium", "S", confidence=0.5, estimated_impact="medium")

        proposals = self.manager.list_proposals()
        self.assertEqual(proposals[0].problem_pattern, "High")
        self.assertEqual(proposals[-1].problem_pattern, "Low")

    def test_review_changes_status(self):
        """review() should change status to REVIEWED."""
        proposal = self.manager.propose("P", "S")
        self.manager.review(proposal.id)

        loaded = self.manager.get(proposal.id)
        self.assertEqual(loaded.status, ProposalStatus.REVIEWED.value)
        self.assertTrue(loaded.reviewed_at)

    def test_approve_changes_status_and_logs_decision(self):
        """approve() should change status and log decision."""
        proposal = self.manager.propose("P", "S")
        result = self.manager.approve(proposal.id, notes="Approved")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ProposalStatus.APPROVED.value)
        self.assertEqual(result.reviewer_notes, "Approved")

        # Decision should be logged
        decisions = self.manager._load_decisions()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].proposal_id, proposal.id)
        self.assertEqual(decisions[0].human_decision, "approve")

    def test_reject_requires_reason(self):
        """reject() should raise ValueError if no reason provided."""
        proposal = self.manager.propose("P", "S")
        with self.assertRaises(ValueError):
            self.manager.reject(proposal.id, reason="")

    def test_reject_changes_status_and_logs_decision(self):
        """reject() should change status and log decision."""
        proposal = self.manager.propose("P", "S")
        result = self.manager.reject(proposal.id, reason="Not needed")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ProposalStatus.REJECTED.value)
        self.assertEqual(result.reviewer_notes, "Not needed")

        # Decision should be logged
        decisions = self.manager._load_decisions()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].human_decision, "reject")

    def test_mark_implemented_only_for_approved(self):
        """mark_implemented() should only work for approved proposals."""
        proposal = self.manager.propose("P", "S")

        # Should fail for proposed status
        result = self.manager.mark_implemented(proposal.id)
        self.assertIsNone(result)

        # Approve first
        self.manager.approve(proposal.id)
        result = self.manager.mark_implemented(proposal.id, prd_name="prd-test")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ProposalStatus.IMPLEMENTED.value)
        self.assertEqual(result.implementation_prd, "prd-test")

    def test_archive_only_for_rejected(self):
        """archive() should only work for rejected proposals."""
        proposal = self.manager.propose("P", "S")

        # Should fail for proposed status
        result = self.manager.archive(proposal.id)
        self.assertIsNone(result)

        # Reject first
        self.manager.reject(proposal.id, reason="No")
        result = self.manager.archive(proposal.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ProposalStatus.ARCHIVED.value)

    def test_generate_digest(self):
        """generate_digest() should return summary statistics."""
        self.manager.propose("P1", "S1", estimated_impact="high")
        self.manager.propose("P2", "S2", estimated_impact="medium", affected_domains=["web"])

        digest = self.manager.generate_digest(days=7)

        self.assertEqual(digest["total_pending"], 2)
        self.assertEqual(digest["by_impact"]["high"], 1)
        self.assertEqual(digest["by_impact"]["medium"], 1)

    def test_get_statistics(self):
        """get_statistics() should return queue statistics."""
        self.manager.propose("P1", "S1")
        p2 = self.manager.propose("P2", "S2")
        self.manager.approve(p2.id)

        stats = self.manager.get_statistics()

        self.assertEqual(stats["total_proposals"], 2)
        self.assertEqual(stats["by_status"]["proposed"], 1)
        self.assertEqual(stats["by_status"]["approved"], 1)

    def test_get_calibration_metrics_empty(self):
        """get_calibration_metrics() should handle empty decisions."""
        metrics = self.manager.get_calibration_metrics()
        self.assertEqual(metrics["total_decisions"], 0)

    def test_get_calibration_metrics_with_decisions(self):
        """get_calibration_metrics() should calculate alignment."""
        # Create and approve proposals
        for i in range(5):
            p = self.manager.propose(f"Problem {i}", "Solution", confidence=0.8)
            self.manager.approve(p.id)

        metrics = self.manager.get_calibration_metrics()

        self.assertEqual(metrics["total_decisions"], 5)
        self.assertEqual(metrics["approval_rate"], 1.0)
        self.assertFalse(metrics["autonomous_threshold_met"])  # Need 50+ decisions

    def test_persistence_across_instances(self):
        """Queue should persist across manager instances."""
        # Create with first manager
        proposal = self.manager.propose("Persistent", "Solution")
        proposal_id = proposal.id

        # Create new manager with same base dir
        new_manager = ImprovementQueueManager(base_dir=Path(self.temp_dir))
        loaded = new_manager.get(proposal_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.problem_pattern, "Persistent")


class TestStatusLifecycle(unittest.TestCase):
    """Tests for the complete status lifecycle."""

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ImprovementQueueManager(base_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_approval_workflow(self):
        """Test: proposed -> reviewed -> approved -> implemented."""
        proposal = self.manager.propose("P", "S")
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED.value)

        self.manager.review(proposal.id)
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.REVIEWED.value)

        self.manager.approve(proposal.id, notes="OK")
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.APPROVED.value)

        self.manager.mark_implemented(proposal.id, prd_name="prd-x")
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.IMPLEMENTED.value)

    def test_rejection_workflow(self):
        """Test: proposed -> reviewed -> rejected -> archived."""
        proposal = self.manager.propose("P", "S")
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED.value)

        self.manager.review(proposal.id)
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.REVIEWED.value)

        self.manager.reject(proposal.id, reason="No")
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.REJECTED.value)

        self.manager.archive(proposal.id)
        proposal = self.manager.get(proposal.id)
        self.assertEqual(proposal.status, ProposalStatus.ARCHIVED.value)


if __name__ == "__main__":
    unittest.main()
