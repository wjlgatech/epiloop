#!/usr/bin/env python3
"""
pattern-clustering.py - Human-Assisted Pattern Clustering for claude-loop

Clusters improvements by problem similarity with mandatory human review for all
uncertain clusters. This ensures humans validate generalizations before any
automatic compression of improvements.

Key Principle: NO automatic compression - humans decide what generalizes.

Features:
- Embedding-based similarity clustering (requires sentence-transformers)
- ClusterProposal with confidence scoring
- Mandatory human review for clusters with confidence < 0.8
- Cluster accuracy tracking (human agreement with proposed clusters)
- Weekly surfacing of uncertain clusters for validation
- CLI for cluster management and review

Usage:
    # Show proposed clusters
    python lib/pattern-clustering.py clusters

    # Review a specific cluster
    python lib/pattern-clustering.py cluster review <cluster_id>

    # Approve a cluster with generalization text
    python lib/pattern-clustering.py cluster approve <cluster_id> --generalization "text"

    # Reject a cluster with reason
    python lib/pattern-clustering.py cluster reject <cluster_id> --reason "reason"

    # Show clustering accuracy stats
    python lib/pattern-clustering.py accuracy

    # Run clustering analysis
    python lib/pattern-clustering.py analyze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any

# Try to import sentence-transformers for embeddings
EMBEDDINGS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Constants
# ============================================================================

DEFAULT_QUEUE_FILE = ".claude-loop/improvement_queue.json"
DEFAULT_CLUSTERS_FILE = ".claude-loop/pattern_clusters.json"
DEFAULT_CLUSTER_DECISIONS_FILE = ".claude-loop/cluster_decisions.jsonl"
BASE_DIR = Path.cwd()

# Clustering configuration
MIN_CLUSTER_SIZE = 2  # Minimum improvements to form a cluster
SIMILARITY_THRESHOLD = 0.65  # Minimum similarity for clustering
HIGH_CONFIDENCE_THRESHOLD = 0.8  # Above this = high confidence
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ============================================================================
# Enums
# ============================================================================

class ClusterStatus(str, Enum):
    """Status lifecycle for cluster proposals."""
    PROPOSED = "proposed"  # Initial state, awaiting review
    APPROVED = "approved"  # Human approved the cluster
    REJECTED = "rejected"  # Human rejected the cluster
    MERGED = "merged"  # Cluster was merged with approved generalization

    def __str__(self) -> str:
        return self.value


class ClusterDecisionType(str, Enum):
    """Types of cluster review decisions."""
    APPROVE = "approve"
    REJECT = "reject"
    SPLIT = "split"  # Split into multiple clusters
    MODIFY = "modify"  # Modify membership

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ClusterMember:
    """A member of a cluster (improvement proposal reference)."""
    proposal_id: str
    problem_pattern: str
    proposed_solution: str
    similarity_to_centroid: float = 0.0
    domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClusterMember":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ClusterProposal:
    """A proposed cluster of similar improvements awaiting human validation.

    Attributes:
        cluster_id: Unique identifier (CLU-XXXXXXXX)
        member_improvements: List of improvement proposals in this cluster
        proposed_generalization: System-proposed generalization of the pattern
        confidence: System confidence in this cluster (0.0-1.0)
        requires_human_validation: True if confidence < 0.8
        status: Current lifecycle status
        created_at: ISO timestamp of creation
        reviewed_at: ISO timestamp when reviewed (if applicable)
        reviewer_notes: Human reviewer's notes
        approved_generalization: Human-approved generalization text
        centroid_text: The text representing cluster centroid
        average_similarity: Average pairwise similarity in cluster
        domain_coverage: Domains covered by cluster members
    """
    cluster_id: str
    member_improvements: list[ClusterMember] = field(default_factory=list)
    proposed_generalization: str = ""
    confidence: float = 0.0
    requires_human_validation: bool = True
    status: str = ClusterStatus.PROPOSED.value
    created_at: str = ""
    reviewed_at: str = ""
    reviewer_notes: str = ""
    approved_generalization: str = ""
    centroid_text: str = ""
    average_similarity: float = 0.0
    domain_coverage: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.cluster_id:
            self.cluster_id = self._generate_id()
        # Calculate requires_human_validation based on confidence
        self.requires_human_validation = self.confidence < HIGH_CONFIDENCE_THRESHOLD

    def _generate_id(self) -> str:
        """Generate unique ID from member IDs and timestamp."""
        member_ids = sorted([m.proposal_id for m in self.member_improvements])
        hash_input = f"{'|'.join(member_ids)}:{self.created_at}"
        hash_hex = hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()
        return f"CLU-{hash_hex}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClusterProposal":
        # Handle nested ClusterMember objects
        if "member_improvements" in data:
            data["member_improvements"] = [
                ClusterMember.from_dict(m) if isinstance(m, dict) else m
                for m in data["member_improvements"]
            ]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_actionable(self) -> bool:
        """Check if cluster is in a state that allows action."""
        return self.status == ClusterStatus.PROPOSED.value


@dataclass
class ClusterDecision:
    """Record of a cluster review decision for accuracy tracking.

    Attributes:
        cluster_id: Which cluster was decided
        decision_type: approve/reject/split/modify
        system_confidence: System's original confidence
        human_decision: What the human decided
        agreement: Whether human agreed with system proposal
        reasoning: Human's reasoning for the decision
        timestamp: When the decision was made
        reviewer_id: Identifier for the reviewer (optional)
    """
    cluster_id: str
    decision_type: str
    system_confidence: float = 0.0
    human_decision: str = ""
    agreement: bool = True
    reasoning: str = ""
    timestamp: str = ""
    reviewer_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # Calculate agreement based on confidence vs decision
        # High confidence should mean approval, low confidence should mean rejection or review
        if self.system_confidence >= HIGH_CONFIDENCE_THRESHOLD:
            self.agreement = self.decision_type == ClusterDecisionType.APPROVE.value
        else:
            # For low confidence, rejection or modification is expected
            self.agreement = self.decision_type in (
                ClusterDecisionType.REJECT.value,
                ClusterDecisionType.SPLIT.value,
                ClusterDecisionType.MODIFY.value
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClusterDecision":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# Pattern Clustering Manager
# ============================================================================

class PatternClusteringManager:
    """Manages pattern clustering with human-in-the-loop validation.

    NO automatic compression - all cluster proposals require human review.
    Tracks clustering accuracy to measure system-human alignment.
    """

    def __init__(
        self,
        queue_file: str = DEFAULT_QUEUE_FILE,
        clusters_file: str = DEFAULT_CLUSTERS_FILE,
        decisions_file: str = DEFAULT_CLUSTER_DECISIONS_FILE,
        base_dir: Path | None = None
    ):
        self.base_dir = base_dir or BASE_DIR
        self.queue_file = self.base_dir / queue_file
        self.clusters_file = self.base_dir / clusters_file
        self.decisions_file = self.base_dir / decisions_file
        self._clusters: dict[str, ClusterProposal] = {}
        self._embedding_model = None
        self._load_clusters()

    def _ensure_dir(self) -> None:
        """Ensure the clusters directory exists."""
        self.clusters_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_clusters(self) -> None:
        """Load clusters from disk."""
        if self.clusters_file.exists():
            try:
                data = json.loads(self.clusters_file.read_text())
                self._clusters = {
                    k: ClusterProposal.from_dict(v)
                    for k, v in data.get("clusters", {}).items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load clusters: {e}", file=sys.stderr)
                self._clusters = {}
        else:
            self._clusters = {}

    def _save_clusters(self) -> None:
        """Persist clusters to disk."""
        self._ensure_dir()
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "clusters": {k: v.to_dict() for k, v in self._clusters.items()}
        }
        self.clusters_file.write_text(json.dumps(data, indent=2))

    def _log_decision(self, decision: ClusterDecision) -> None:
        """Append decision to decisions log for accuracy tracking."""
        self._ensure_dir()
        with open(self.decisions_file, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    def _load_improvement_queue(self) -> dict[str, Any]:
        """Load improvement proposals from the queue."""
        if not self.queue_file.exists():
            return {}

        try:
            data = json.loads(self.queue_file.read_text())
            return data.get("proposals", {})
        except (json.JSONDecodeError, KeyError):
            return {}

    def _get_embedding_model(self):
        """Get or initialize the embedding model."""
        if self._embedding_model is None and EMBEDDINGS_AVAILABLE:
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedding_model

    def _compute_embedding(self, text: str) -> list[float] | None:
        """Compute embedding for text using sentence-transformers."""
        model = self._get_embedding_model()
        if model is None:
            return None
        embedding = model.encode([text])[0]
        return embedding.tolist()

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts.

        Uses embedding similarity if available, falls back to text similarity.
        """
        if EMBEDDINGS_AVAILABLE:
            model = self._get_embedding_model()
            if model:
                embeddings = model.encode([text1, text2])
                # Cosine similarity
                similarity = float(np.dot(embeddings[0], embeddings[1]) /
                                 (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])))
                return max(0.0, min(1.0, similarity))

        # Fallback: text-based similarity using SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _generate_generalization(self, members: list[ClusterMember]) -> str:
        """Generate a proposed generalization for cluster members.

        Identifies common patterns in problem descriptions.
        """
        if not members:
            return ""

        # Extract key terms from all problems
        all_problems = [m.problem_pattern for m in members]

        # Find common words across all problems
        word_sets = [set(p.lower().split()) for p in all_problems]
        common_words = word_sets[0]
        for ws in word_sets[1:]:
            common_words &= ws

        # Remove common stop words
        stop_words = {"a", "an", "the", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "must", "can",
                      "in", "on", "at", "to", "for", "of", "with", "by", "from",
                      "and", "or", "but", "if", "then", "so", "than", "when",
                      "that", "this", "these", "those", "it", "its"}
        common_words -= stop_words

        if common_words:
            common_part = ", ".join(sorted(common_words)[:5])
            return f"Pattern involving: {common_part} (affects {len(members)} improvements)"

        # Fallback: use first problem as base
        return f"Similar to: {all_problems[0][:100]}... ({len(members)} related improvements)"

    def _calculate_cluster_confidence(
        self,
        members: list[ClusterMember],
        similarities: list[float]
    ) -> float:
        """Calculate confidence score for a cluster.

        Higher confidence when:
        - Higher average similarity
        - More members
        - More consistent similarity (lower variance)
        """
        if not similarities:
            return 0.0

        avg_similarity = sum(similarities) / len(similarities)
        size_factor = min(len(members) / 5, 1.0)  # Max bonus at 5 members

        # Variance penalty
        if len(similarities) > 1:
            variance = sum((s - avg_similarity) ** 2 for s in similarities) / len(similarities)
            consistency = max(0, 1 - variance)
        else:
            consistency = 0.5  # Neutral for single pair

        # Weighted combination
        confidence = (avg_similarity * 0.6) + (size_factor * 0.2) + (consistency * 0.2)
        return round(min(1.0, max(0.0, confidence)), 3)

    # =========================================================================
    # Clustering Operations
    # =========================================================================

    def analyze_and_cluster(
        self,
        min_cluster_size: int = MIN_CLUSTER_SIZE,
        similarity_threshold: float = SIMILARITY_THRESHOLD
    ) -> list[ClusterProposal]:
        """Analyze improvements and create cluster proposals.

        Uses embedding-based similarity to group related improvements.
        NO automatic compression - all proposals require human review.

        Args:
            min_cluster_size: Minimum members for a valid cluster
            similarity_threshold: Minimum similarity to include in cluster

        Returns:
            List of new cluster proposals
        """
        proposals = self._load_improvement_queue()
        if not proposals:
            return []

        # Filter to proposed/reviewed status only
        active_proposals = {
            k: v for k, v in proposals.items()
            if v.get("status") in ("proposed", "reviewed")
        }

        if len(active_proposals) < min_cluster_size:
            return []

        # Build similarity matrix
        proposal_ids = list(active_proposals.keys())
        problem_texts = [
            f"{active_proposals[pid]['problem_pattern']} {active_proposals[pid]['proposed_solution']}"
            for pid in proposal_ids
        ]

        # Compute pairwise similarities
        similarities: dict[tuple[str, str], float] = {}
        for i, pid1 in enumerate(proposal_ids):
            for j, pid2 in enumerate(proposal_ids):
                if i < j:
                    sim = self._compute_similarity(problem_texts[i], problem_texts[j])
                    similarities[(pid1, pid2)] = sim

        # Greedy clustering (simple agglomerative approach)
        clusters: list[set[str]] = []
        assigned: set[str] = set()

        # Sort pairs by similarity (descending)
        sorted_pairs = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for (pid1, pid2), sim in sorted_pairs:
            if sim < similarity_threshold:
                break

            # Find clusters containing these IDs
            cluster1 = next((c for c in clusters if pid1 in c), None)
            cluster2 = next((c for c in clusters if pid2 in c), None)

            if cluster1 is None and cluster2 is None:
                # Create new cluster
                clusters.append({pid1, pid2})
                assigned.add(pid1)
                assigned.add(pid2)
            elif cluster1 is not None and cluster2 is None:
                cluster1.add(pid2)
                assigned.add(pid2)
            elif cluster1 is None and cluster2 is not None:
                cluster2.add(pid1)
                assigned.add(pid1)
            elif cluster1 is not None and cluster2 is not None and cluster1 is not cluster2:
                # Merge clusters if average similarity stays high
                merged = cluster1 | cluster2
                # Calculate average similarity in merged cluster
                merged_sims = []
                for m1 in merged:
                    for m2 in merged:
                        if m1 < m2:
                            key = (m1, m2) if m1 < m2 else (m2, m1)
                            if key in similarities:
                                merged_sims.append(similarities[key])

                avg_sim = sum(merged_sims) / len(merged_sims) if merged_sims else 0
                if avg_sim >= similarity_threshold:
                    clusters.remove(cluster1)
                    clusters.remove(cluster2)
                    clusters.append(merged)

        # Create ClusterProposal objects
        new_clusters: list[ClusterProposal] = []

        for cluster_members in clusters:
            if len(cluster_members) < min_cluster_size:
                continue

            # Check if similar cluster already exists
            existing = self._find_similar_cluster(cluster_members)
            if existing:
                continue

            # Build cluster member objects
            members: list[ClusterMember] = []
            member_similarities: list[float] = []
            all_domains: set[str] = set()

            for pid in cluster_members:
                proposal = active_proposals[pid]
                domains = proposal.get("affected_domains", [])
                all_domains.update(domains)

                # Calculate similarity to other members
                sims_to_others = []
                for other_pid in cluster_members:
                    if pid != other_pid:
                        key = (min(pid, other_pid), max(pid, other_pid))
                        if key in similarities:
                            sims_to_others.append(similarities[key])

                avg_sim_to_others = sum(sims_to_others) / len(sims_to_others) if sims_to_others else 0
                member_similarities.append(avg_sim_to_others)

                members.append(ClusterMember(
                    proposal_id=pid,
                    problem_pattern=proposal.get("problem_pattern", ""),
                    proposed_solution=proposal.get("proposed_solution", ""),
                    similarity_to_centroid=avg_sim_to_others,
                    domains=domains
                ))

            # Calculate confidence and generate proposal
            confidence = self._calculate_cluster_confidence(members, member_similarities)
            generalization = self._generate_generalization(members)

            # Find centroid (member with highest average similarity to others)
            centroid_idx = member_similarities.index(max(member_similarities)) if member_similarities else 0
            centroid_text = members[centroid_idx].problem_pattern if members else ""

            cluster = ClusterProposal(
                cluster_id="",  # Will be generated
                member_improvements=members,
                proposed_generalization=generalization,
                confidence=confidence,
                centroid_text=centroid_text,
                average_similarity=sum(member_similarities) / len(member_similarities) if member_similarities else 0,
                domain_coverage=sorted(all_domains)
            )

            self._clusters[cluster.cluster_id] = cluster
            new_clusters.append(cluster)

        self._save_clusters()
        return new_clusters

    def _find_similar_cluster(self, member_ids: set[str]) -> ClusterProposal | None:
        """Find an existing cluster with similar members."""
        for cluster in self._clusters.values():
            existing_ids = {m.proposal_id for m in cluster.member_improvements}
            # Check overlap
            overlap = len(member_ids & existing_ids) / max(len(member_ids), len(existing_ids))
            if overlap > 0.7:
                return cluster
        return None

    # =========================================================================
    # Cluster Management
    # =========================================================================

    def get(self, cluster_id: str) -> ClusterProposal | None:
        """Get a cluster by ID."""
        return self._clusters.get(cluster_id)

    def list_clusters(
        self,
        status: str | None = None,
        requires_validation: bool | None = None
    ) -> list[ClusterProposal]:
        """List clusters with optional filters.

        Args:
            status: Filter by status
            requires_validation: Filter by validation requirement

        Returns:
            List of matching clusters sorted by confidence (ascending for review priority)
        """
        results = []
        for cluster in self._clusters.values():
            if status and cluster.status != status:
                continue
            if requires_validation is not None and cluster.requires_human_validation != requires_validation:
                continue
            results.append(cluster)

        # Sort by confidence (ascending) so low-confidence clusters are reviewed first
        return sorted(results, key=lambda c: c.confidence)

    def list_pending(self) -> list[ClusterProposal]:
        """List all clusters awaiting human review."""
        return self.list_clusters(status=ClusterStatus.PROPOSED.value)

    def list_requiring_validation(self) -> list[ClusterProposal]:
        """List clusters requiring mandatory human validation (confidence < 0.8)."""
        return [
            c for c in self.list_pending()
            if c.requires_human_validation
        ]

    def approve(
        self,
        cluster_id: str,
        generalization: str,
        notes: str = "",
        reviewer_id: str = ""
    ) -> ClusterProposal | None:
        """Approve a cluster with human-provided generalization.

        Args:
            cluster_id: ID of the cluster to approve
            generalization: Human-approved generalization text (required)
            notes: Additional reviewer notes
            reviewer_id: Optional reviewer identifier

        Returns:
            The approved cluster or None if not found/invalid state
        """
        if not generalization:
            raise ValueError("Generalization text is required for approval")

        cluster = self.get(cluster_id)
        if not cluster or not cluster.is_actionable():
            return None

        cluster.status = ClusterStatus.APPROVED.value
        cluster.reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cluster.reviewer_notes = notes
        cluster.approved_generalization = generalization
        self._save_clusters()

        # Log decision for accuracy tracking
        decision = ClusterDecision(
            cluster_id=cluster_id,
            decision_type=ClusterDecisionType.APPROVE.value,
            system_confidence=cluster.confidence,
            human_decision="approve",
            reasoning=f"{notes}. Generalization: {generalization}",
            reviewer_id=reviewer_id
        )
        self._log_decision(decision)

        return cluster

    def reject(
        self,
        cluster_id: str,
        reason: str,
        reviewer_id: str = ""
    ) -> ClusterProposal | None:
        """Reject a cluster with reason.

        Args:
            cluster_id: ID of the cluster to reject
            reason: Required reason for rejection
            reviewer_id: Optional reviewer identifier

        Returns:
            The rejected cluster or None if not found/invalid state
        """
        if not reason:
            raise ValueError("Rejection reason is required")

        cluster = self.get(cluster_id)
        if not cluster or not cluster.is_actionable():
            return None

        cluster.status = ClusterStatus.REJECTED.value
        cluster.reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cluster.reviewer_notes = reason
        self._save_clusters()

        # Log decision for accuracy tracking
        decision = ClusterDecision(
            cluster_id=cluster_id,
            decision_type=ClusterDecisionType.REJECT.value,
            system_confidence=cluster.confidence,
            human_decision="reject",
            reasoning=reason,
            reviewer_id=reviewer_id
        )
        self._log_decision(decision)

        return cluster

    def mark_merged(
        self,
        cluster_id: str,
        merged_proposal_id: str = ""
    ) -> ClusterProposal | None:
        """Mark an approved cluster as merged into a generalized improvement.

        Args:
            cluster_id: ID of the cluster
            merged_proposal_id: ID of the merged improvement proposal

        Returns:
            The updated cluster or None if not found/invalid state
        """
        cluster = self.get(cluster_id)
        if not cluster or cluster.status != ClusterStatus.APPROVED.value:
            return None

        cluster.status = ClusterStatus.MERGED.value
        # Store merged proposal ID in reviewer notes if provided
        if merged_proposal_id:
            cluster.reviewer_notes = f"{cluster.reviewer_notes} Merged to: {merged_proposal_id}".strip()
        self._save_clusters()

        return cluster

    # =========================================================================
    # Accuracy Tracking
    # =========================================================================

    def _load_decisions(self) -> list[ClusterDecision]:
        """Load all decisions from the decisions log."""
        decisions = []
        if self.decisions_file.exists():
            for line in self.decisions_file.read_text().splitlines():
                if line.strip():
                    try:
                        decisions.append(ClusterDecision.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        return decisions

    def get_accuracy_metrics(self) -> dict[str, Any]:
        """Get clustering accuracy metrics.

        Measures how well the system's clustering proposals align with
        human decisions.

        Returns:
            Accuracy metrics including agreement rates
        """
        decisions = self._load_decisions()
        if not decisions:
            return {
                "total_decisions": 0,
                "agreement_rate": 0.0,
                "message": "No cluster decisions recorded yet"
            }

        # Agreement: high confidence -> approved, low confidence -> rejected/modified
        agreements = sum(1 for d in decisions if d.agreement)
        approvals = sum(1 for d in decisions if d.human_decision == "approve")
        rejections = sum(1 for d in decisions if d.human_decision == "reject")

        # High confidence clusters that were approved
        high_conf_approved = sum(
            1 for d in decisions
            if d.system_confidence >= HIGH_CONFIDENCE_THRESHOLD
            and d.decision_type == ClusterDecisionType.APPROVE.value
        )
        high_conf_total = sum(
            1 for d in decisions
            if d.system_confidence >= HIGH_CONFIDENCE_THRESHOLD
        )

        # Low confidence clusters that were rejected/modified
        low_conf_rejected = sum(
            1 for d in decisions
            if d.system_confidence < HIGH_CONFIDENCE_THRESHOLD
            and d.decision_type in (ClusterDecisionType.REJECT.value, ClusterDecisionType.MODIFY.value)
        )
        low_conf_total = sum(
            1 for d in decisions
            if d.system_confidence < HIGH_CONFIDENCE_THRESHOLD
        )

        total = len(decisions)

        return {
            "total_decisions": total,
            "agreement_rate": round(agreements / total, 3),
            "approval_rate": round(approvals / total, 3),
            "rejection_rate": round(rejections / total, 3),
            "high_confidence_accuracy": round(high_conf_approved / max(high_conf_total, 1), 3),
            "low_confidence_accuracy": round(low_conf_rejected / max(low_conf_total, 1), 3),
            "message": (
                f"Clustering accuracy: {agreements}/{total} ({round(agreements/total*100, 1)}%). "
                f"High-confidence: {high_conf_approved}/{high_conf_total}, "
                f"Low-confidence flagged: {low_conf_rejected}/{low_conf_total}."
            )
        }

    def get_weekly_uncertain_clusters(self) -> list[ClusterProposal]:
        """Get clusters requiring validation that are at least 1 week old.

        Surfaces old uncertain clusters for human attention.
        """
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
        uncertain = []

        for cluster in self._clusters.values():
            if cluster.status != ClusterStatus.PROPOSED.value:
                continue
            if not cluster.requires_human_validation:
                continue

            created = datetime.fromisoformat(cluster.created_at.rstrip("Z"))
            if created <= cutoff:
                uncertain.append(cluster)

        return sorted(uncertain, key=lambda c: c.created_at)

    def get_statistics(self) -> dict[str, Any]:
        """Get clustering statistics for monitoring.

        Returns:
            Statistics including counts by status, confidence distribution, etc.
        """
        by_status: dict[str, int] = {}
        confidence_sum = 0.0
        requiring_validation = 0
        total_members = 0

        for cluster in self._clusters.values():
            status = cluster.status
            by_status[status] = by_status.get(status, 0) + 1
            confidence_sum += cluster.confidence
            if cluster.requires_human_validation and cluster.status == ClusterStatus.PROPOSED.value:
                requiring_validation += 1
            total_members += len(cluster.member_improvements)

        total_clusters = len(self._clusters)

        return {
            "total_clusters": total_clusters,
            "by_status": by_status,
            "average_confidence": round(confidence_sum / max(total_clusters, 1), 3),
            "pending_count": by_status.get(ClusterStatus.PROPOSED.value, 0),
            "approved_count": by_status.get(ClusterStatus.APPROVED.value, 0),
            "rejected_count": by_status.get(ClusterStatus.REJECTED.value, 0),
            "merged_count": by_status.get(ClusterStatus.MERGED.value, 0),
            "requiring_validation": requiring_validation,
            "total_members": total_members,
            "average_cluster_size": round(total_members / max(total_clusters, 1), 1)
        }


# ============================================================================
# CLI Interface
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Human-Assisted Pattern Clustering for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show proposed clusters
    python lib/pattern-clustering.py clusters

    # Review a specific cluster
    python lib/pattern-clustering.py cluster review CLU-ABC12345

    # Approve a cluster with generalization
    python lib/pattern-clustering.py cluster approve CLU-ABC12345 --generalization "Error handling pattern"

    # Reject a cluster
    python lib/pattern-clustering.py cluster reject CLU-ABC12345 --reason "Not related"

    # Show clustering accuracy
    python lib/pattern-clustering.py accuracy

    # Run clustering analysis
    python lib/pattern-clustering.py analyze
"""
    )

    # Global options
    parser.add_argument(
        "--base-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Base directory for cluster files (default: current directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # clusters subcommand
    clusters_parser = subparsers.add_parser("clusters", help="List proposed clusters")
    clusters_parser.add_argument("--status", "-s", help="Filter by status")
    clusters_parser.add_argument("--validation-required", action="store_true",
                                 help="Only show clusters requiring validation")

    # cluster subcommand
    cluster_parser = subparsers.add_parser("cluster", help="Cluster operations")
    cluster_subparsers = cluster_parser.add_subparsers(dest="cluster_command", help="Cluster commands")

    # cluster review
    review_parser = cluster_subparsers.add_parser("review", help="Review a cluster")
    review_parser.add_argument("id", help="Cluster ID to review")

    # cluster approve
    approve_parser = cluster_subparsers.add_parser("approve", help="Approve a cluster")
    approve_parser.add_argument("id", help="Cluster ID to approve")
    approve_parser.add_argument("--generalization", "-g", required=True, help="Approved generalization text")
    approve_parser.add_argument("--notes", "-n", default="", help="Additional notes")
    approve_parser.add_argument("--reviewer", "-r", default="", help="Reviewer ID")

    # cluster reject
    reject_parser = cluster_subparsers.add_parser("reject", help="Reject a cluster")
    reject_parser.add_argument("id", help="Cluster ID to reject")
    reject_parser.add_argument("--reason", "-r", required=True, help="Rejection reason (required)")
    reject_parser.add_argument("--reviewer", default="", help="Reviewer ID")

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Run clustering analysis")
    analyze_parser.add_argument("--min-size", type=int, default=MIN_CLUSTER_SIZE,
                                help=f"Minimum cluster size (default: {MIN_CLUSTER_SIZE})")
    analyze_parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD,
                                help=f"Similarity threshold (default: {SIMILARITY_THRESHOLD})")

    # accuracy subcommand
    subparsers.add_parser("accuracy", help="Show clustering accuracy metrics")

    # stats subcommand
    subparsers.add_parser("stats", help="Show clustering statistics")

    # weekly subcommand
    subparsers.add_parser("weekly", help="Show uncertain clusters requiring weekly review")

    return parser


def format_cluster(cluster: ClusterProposal, verbose: bool = False) -> str:
    """Format a cluster for display."""
    validation_marker = " [REQUIRES VALIDATION]" if cluster.requires_human_validation else ""

    lines = [
        f"Cluster ID: {cluster.cluster_id}{validation_marker}",
        f"Status: {cluster.status}",
        f"Confidence: {cluster.confidence:.3f}",
        f"Average Similarity: {cluster.average_similarity:.3f}",
        f"Members: {len(cluster.member_improvements)}",
        "",
        f"Proposed Generalization:",
        f"  {cluster.proposed_generalization}",
    ]

    if cluster.domain_coverage:
        lines.extend(["", f"Domains: {', '.join(cluster.domain_coverage)}"])

    lines.extend(["", "Member Improvements:"])
    for i, member in enumerate(cluster.member_improvements, 1):
        lines.append(f"  {i}. [{member.proposal_id}] sim={member.similarity_to_centroid:.3f}")
        lines.append(f"     Problem: {member.problem_pattern[:60]}...")
        if verbose:
            lines.append(f"     Solution: {member.proposed_solution[:60]}...")

    if verbose:
        lines.extend([
            "",
            f"Created: {cluster.created_at}",
            f"Centroid: {cluster.centroid_text[:80]}...",
        ])
        if cluster.reviewed_at:
            lines.append(f"Reviewed: {cluster.reviewed_at}")
        if cluster.reviewer_notes:
            lines.append(f"Reviewer Notes: {cluster.reviewer_notes}")
        if cluster.approved_generalization:
            lines.append(f"Approved Generalization: {cluster.approved_generalization}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = PatternClusteringManager(base_dir=args.base_dir)

    # Handle commands
    if args.command == "clusters":
        requires_validation = args.validation_required if hasattr(args, 'validation_required') else None
        clusters = manager.list_clusters(
            status=args.status if hasattr(args, 'status') else None,
            requires_validation=True if requires_validation else None
        )

        if args.json:
            print(json.dumps([c.to_dict() for c in clusters], indent=2))
        else:
            if not clusters:
                print("No clusters found matching criteria.")
            else:
                print(f"Found {len(clusters)} cluster(s):\n")
                for c in clusters:
                    validation = " [NEEDS VALIDATION]" if c.requires_human_validation else ""
                    print(f"[{c.cluster_id}] {c.status.upper()}{validation}")
                    print(f"  Confidence: {c.confidence:.3f} | Members: {len(c.member_improvements)}")
                    print(f"  {c.proposed_generalization[:60]}...")
                    print()
        return 0

    elif args.command == "cluster":
        if not args.cluster_command:
            parser.parse_args(["cluster", "--help"])
            return 1

        if args.cluster_command == "review":
            cluster = manager.get(args.id)
            if not cluster:
                print(f"Cluster {args.id} not found.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(cluster.to_dict(), indent=2))
            else:
                print(format_cluster(cluster, verbose=args.verbose))
                print()
                print("-" * 60)
                if cluster.is_actionable():
                    print("Actions available:")
                    print(f"  Approve: python lib/pattern-clustering.py cluster approve {args.id} --generalization 'text'")
                    print(f"  Reject:  python lib/pattern-clustering.py cluster reject {args.id} --reason 'reason'")
                else:
                    print(f"No actions available (status: {cluster.status})")
            return 0

        elif args.cluster_command == "approve":
            try:
                cluster = manager.approve(
                    args.id,
                    generalization=args.generalization,
                    notes=args.notes,
                    reviewer_id=args.reviewer
                )
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

            if not cluster:
                print(f"Cannot approve {args.id} - not found or not actionable.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(cluster.to_dict(), indent=2))
            else:
                print(f"Cluster {args.id} APPROVED")
                print(f"Generalization: {args.generalization}")
                if args.notes:
                    print(f"Notes: {args.notes}")
            return 0

        elif args.cluster_command == "reject":
            try:
                cluster = manager.reject(args.id, reason=args.reason, reviewer_id=args.reviewer)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

            if not cluster:
                print(f"Cannot reject {args.id} - not found or not actionable.", file=sys.stderr)
                return 1

            if args.json:
                print(json.dumps(cluster.to_dict(), indent=2))
            else:
                print(f"Cluster {args.id} REJECTED")
                print(f"Reason: {args.reason}")
            return 0

    elif args.command == "analyze":
        print("Running clustering analysis...")
        if not EMBEDDINGS_AVAILABLE:
            print("Warning: sentence-transformers not available. Using text-based similarity.")

        new_clusters = manager.analyze_and_cluster(
            min_cluster_size=args.min_size,
            similarity_threshold=args.threshold
        )

        if args.json:
            print(json.dumps([c.to_dict() for c in new_clusters], indent=2))
        else:
            print(f"\nFound {len(new_clusters)} new cluster(s):")
            for c in new_clusters:
                validation = " [NEEDS VALIDATION]" if c.requires_human_validation else ""
                print(f"  [{c.cluster_id}] {len(c.member_improvements)} members, confidence={c.confidence:.3f}{validation}")
            if new_clusters:
                print("\nUse 'python lib/pattern-clustering.py clusters' to see all clusters.")
                print("Use 'python lib/pattern-clustering.py cluster review <id>' to review a cluster.")
        return 0

    elif args.command == "accuracy":
        metrics = manager.get_accuracy_metrics()

        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print("=== Clustering Accuracy ===")
            print(metrics['message'])
            print()
            if metrics['total_decisions'] > 0:
                print(f"Total Decisions: {metrics['total_decisions']}")
                print(f"Agreement Rate: {metrics['agreement_rate']*100:.1f}%")
                print(f"Approval Rate: {metrics['approval_rate']*100:.1f}%")
                print(f"Rejection Rate: {metrics['rejection_rate']*100:.1f}%")
                print()
                print("Confidence Calibration:")
                print(f"  High-confidence accuracy: {metrics['high_confidence_accuracy']*100:.1f}%")
                print(f"  Low-confidence flagging: {metrics['low_confidence_accuracy']*100:.1f}%")
        return 0

    elif args.command == "stats":
        stats = manager.get_statistics()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("=== Clustering Statistics ===")
            print(f"Total Clusters: {stats['total_clusters']}")
            print(f"Average Confidence: {stats['average_confidence']:.3f}")
            print(f"Average Cluster Size: {stats['average_cluster_size']:.1f}")
            print(f"Total Members: {stats['total_members']}")
            print()
            print("By Status:")
            for status, count in stats['by_status'].items():
                print(f"  {status}: {count}")
            print()
            print(f"Requiring Validation: {stats['requiring_validation']}")
        return 0

    elif args.command == "weekly":
        clusters = manager.get_weekly_uncertain_clusters()

        if args.json:
            print(json.dumps([c.to_dict() for c in clusters], indent=2))
        else:
            if not clusters:
                print("No uncertain clusters requiring weekly review.")
            else:
                print(f"=== Weekly Review: {len(clusters)} Uncertain Cluster(s) ===")
                print("These clusters have low confidence and are at least 1 week old.\n")
                for c in clusters:
                    print(f"[{c.cluster_id}] Created: {c.created_at[:10]}")
                    print(f"  Confidence: {c.confidence:.3f} | Members: {len(c.member_improvements)}")
                    print(f"  {c.proposed_generalization[:60]}...")
                    print()
                print("Review these clusters to improve clustering accuracy.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
