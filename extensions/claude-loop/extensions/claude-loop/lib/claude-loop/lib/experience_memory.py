#!/usr/bin/env python3
"""
Experience Memory - Contextual Experience Replay (CER) Storage for Research Loop

This module provides experience storage and retrieval for the research loop system.
It enables learning from past research sessions to improve future research quality.

Features:
- Store research experiences with full context
- Similarity-based retrieval for relevant past experiences
- Pattern compression for efficient reuse
- Domain-aware storage and retrieval
- CLI interface for manual operations

Usage:
    # Store an experience
    python lib/experience_memory.py store --query "..." --findings "..." --domain ai-ml

    # Retrieve similar experiences
    python lib/experience_memory.py retrieve --query "..." --k 5

    # Get statistics
    python lib/experience_memory.py stats
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re

# Try to import optional dependencies for embeddings
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Constants
# ============================================================================

DEFAULT_STORAGE_PATH = ".claude-loop/data/experiences.json"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Experience:
    """Represents a single research experience."""
    id: str
    query: str  # Original research query
    domain: str  # ai-ml, investment, general
    sub_questions: List[str]  # How the query was decomposed
    findings: List[Dict]  # What was found (content, source, relevance)
    synthesis: str  # Final synthesis text
    confidence: int  # 0-100 confidence score
    outcome: Optional[str] = None  # Actual result for learning
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    compressed_pattern: str = ""  # Compressed learnings
    embedding: Optional[List[float]] = None  # Vector embedding for similarity search
    retrieval_count: int = 0  # How many times this was retrieved
    helpful_count: int = 0  # How many times this was marked helpful

    def to_dict(self) -> Dict:
        """Convert experience to dictionary for JSON storage."""
        return {
            'id': self.id,
            'query': self.query,
            'domain': self.domain,
            'sub_questions': self.sub_questions,
            'findings': self.findings,
            'synthesis': self.synthesis,
            'confidence': self.confidence,
            'outcome': self.outcome,
            'timestamp': self.timestamp,
            'compressed_pattern': self.compressed_pattern,
            'embedding': self.embedding,
            'retrieval_count': self.retrieval_count,
            'helpful_count': self.helpful_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Experience':
        """Create Experience from dictionary."""
        return cls(
            id=data['id'],
            query=data['query'],
            domain=data.get('domain', 'general'),
            sub_questions=data.get('sub_questions', []),
            findings=data.get('findings', []),
            synthesis=data.get('synthesis', ''),
            confidence=data.get('confidence', 0),
            outcome=data.get('outcome'),
            timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            compressed_pattern=data.get('compressed_pattern', ''),
            embedding=data.get('embedding'),
            retrieval_count=data.get('retrieval_count', 0),
            helpful_count=data.get('helpful_count', 0)
        )


@dataclass
class RetrievalResult:
    """Result of experience retrieval with similarity score."""
    experience: Experience
    similarity: float  # 0.0-1.0 similarity score

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'experience': self.experience.to_dict(),
            'similarity': self.similarity
        }


# ============================================================================
# Embedding Utilities
# ============================================================================

class EmbeddingProvider:
    """Provides embeddings using sentence-transformers or fallback hash method."""

    def __init__(self):
        self._model = None
        self._use_semantic = SENTENCE_TRANSFORMERS_AVAILABLE

    def _load_model(self):
        """Lazy load the embedding model."""
        if self._model is None and self._use_semantic:
            try:
                self._model = SentenceTransformer(EMBEDDING_MODEL)
            except Exception:
                self._use_semantic = False

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Uses sentence-transformers if available, otherwise falls back to
        a deterministic hash-based embedding.
        """
        if self._use_semantic:
            self._load_model()
            if self._model is not None:
                embedding = self._model.encode(text, convert_to_numpy=True)
                return embedding.tolist()

        # Fallback: hash-based embedding
        return self._hash_embedding(text)

    def _hash_embedding(self, text: str) -> List[float]:
        """
        Generate a deterministic hash-based embedding.

        This is a fallback when sentence-transformers is not available.
        Not as semantically meaningful but deterministic and fast.
        """
        # Normalize text
        normalized = text.lower().strip()

        # Generate multiple hashes for different aspects
        embedding = []
        for i in range(EMBEDDING_DIM):
            seed = f"{normalized}:{i}"
            hash_val = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
            # Normalize to [-1, 1] range
            normalized_val = ((hash_val % 10000) / 5000.0) - 1.0
            embedding.append(normalized_val)

        # Normalize to unit length
        magnitude = math.sqrt(sum(x*x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Returns value in range [-1, 1], where 1 is identical.
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# ============================================================================
# Experience Memory Class
# ============================================================================

class ExperienceMemory:
    """
    Manages storage and retrieval of research experiences.

    Provides:
    - Persistent JSON storage
    - Similarity-based retrieval using embeddings
    - Domain filtering
    - Pattern compression
    - Statistics tracking
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize experience memory.

        Args:
            storage_path: Path to JSON storage file (default: .claude-loop/data/experiences.json)
        """
        if storage_path is None:
            storage_path = DEFAULT_STORAGE_PATH

        self.storage_path = Path(storage_path)
        self.embedding_provider = EmbeddingProvider()
        self._experiences: Dict[str, Experience] = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Ensure experiences are loaded from disk."""
        if not self._loaded:
            self._load()

    def _load(self):
        """Load experiences from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                # Handle both list and dict formats
                if isinstance(data, list):
                    for exp_data in data:
                        exp = Experience.from_dict(exp_data)
                        self._experiences[exp.id] = exp
                elif isinstance(data, dict):
                    if 'experiences' in data:
                        for exp_data in data['experiences']:
                            exp = Experience.from_dict(exp_data)
                            self._experiences[exp.id] = exp
            except (json.JSONDecodeError, KeyError):
                self._experiences = {}

        self._loaded = True

    def _save(self):
        """Save experiences to JSON file."""
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to list for storage
        data = {
            'version': '1.0',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'experiences': [exp.to_dict() for exp in self._experiences.values()]
        }

        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_id(self, query: str) -> str:
        """Generate unique ID for an experience."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
        return f"EXP-{timestamp}-{query_hash}"

    def store(self, experience: Experience) -> str:
        """
        Store a new experience.

        Args:
            experience: Experience to store

        Returns:
            Experience ID
        """
        self._ensure_loaded()

        # Generate ID if not provided
        if not experience.id:
            experience.id = self._generate_id(experience.query)

        # Generate embedding if not provided
        if experience.embedding is None:
            query_text = f"{experience.domain}: {experience.query}"
            experience.embedding = self.embedding_provider.embed(query_text)

        # Store experience
        self._experiences[experience.id] = experience
        self._save()

        return experience.id

    def retrieve(
        self,
        query: str,
        domain: Optional[str] = None,
        k: int = 5,
        min_similarity: float = 0.3
    ) -> List[RetrievalResult]:
        """
        Retrieve similar past experiences.

        Args:
            query: Query to find similar experiences for
            domain: Filter by domain (optional)
            k: Maximum number of results
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of RetrievalResult ordered by similarity (highest first)
        """
        self._ensure_loaded()

        if not self._experiences:
            return []

        # Generate query embedding
        query_text = f"{domain or 'general'}: {query}"
        query_embedding = self.embedding_provider.embed(query_text)

        # Calculate similarities
        results = []
        for exp in self._experiences.values():
            # Domain filter
            if domain and exp.domain != domain:
                continue

            # Calculate similarity
            if exp.embedding:
                similarity = self.embedding_provider.cosine_similarity(
                    query_embedding, exp.embedding
                )

                # Normalize to 0-1 range (cosine similarity is -1 to 1)
                similarity = (similarity + 1) / 2

                if similarity >= min_similarity:
                    # Update retrieval count
                    exp.retrieval_count += 1
                    results.append(RetrievalResult(
                        experience=exp,
                        similarity=similarity
                    ))

        # Sort by similarity (highest first) and limit
        results.sort(key=lambda r: r.similarity, reverse=True)
        results = results[:k]

        # Save updated retrieval counts
        if results:
            self._save()

        return results

    def get(self, experience_id: str) -> Optional[Experience]:
        """
        Get experience by ID.

        Args:
            experience_id: Experience ID to retrieve

        Returns:
            Experience or None if not found
        """
        self._ensure_loaded()
        return self._experiences.get(experience_id)

    def update(self, experience: Experience) -> bool:
        """
        Update an existing experience.

        Args:
            experience: Experience with updated fields

        Returns:
            True if updated, False if not found
        """
        self._ensure_loaded()

        if experience.id not in self._experiences:
            return False

        self._experiences[experience.id] = experience
        self._save()
        return True

    def mark_helpful(self, experience_id: str) -> bool:
        """
        Mark an experience as helpful (used in learning).

        Args:
            experience_id: ID of experience to mark

        Returns:
            True if marked, False if not found
        """
        self._ensure_loaded()

        if experience_id not in self._experiences:
            return False

        self._experiences[experience_id].helpful_count += 1
        self._save()
        return True

    def compress(self, experience: Experience) -> str:
        """
        Extract reusable patterns from an experience.

        Args:
            experience: Experience to compress

        Returns:
            Compressed pattern string
        """
        patterns = []

        # Extract search strategy patterns
        if experience.sub_questions:
            patterns.append(f"Decomposition: {len(experience.sub_questions)} sub-questions")

            # Identify question types
            types = set()
            for sq in experience.sub_questions:
                sq_lower = sq.lower()
                if any(kw in sq_lower for kw in ['how', 'implement', 'code']):
                    types.add('technical')
                elif any(kw in sq_lower for kw in ['research', 'study', 'paper']):
                    types.add('academic')
                elif any(kw in sq_lower for kw in ['market', 'cost', 'price']):
                    types.add('market')

            if types:
                patterns.append(f"Question types: {', '.join(sorted(types))}")

        # Extract source patterns
        if experience.findings:
            source_types = set()
            for f in experience.findings:
                url = f.get('source_url', '')
                if 'arxiv' in url:
                    source_types.add('arxiv')
                elif 'github' in url:
                    source_types.add('github')
                elif any(news in url for news in ['news', 'blog', 'medium']):
                    source_types.add('news/blog')
                else:
                    source_types.add('web')

            patterns.append(f"Source types: {', '.join(sorted(source_types))}")
            patterns.append(f"Total sources: {len(experience.findings)}")

        # Extract confidence factors
        if experience.confidence >= 75:
            patterns.append("High confidence - good source coverage")
        elif experience.confidence >= 50:
            patterns.append("Moderate confidence - consider more sources")
        else:
            patterns.append("Low confidence - needs deeper research")

        # Combine patterns
        compressed = " | ".join(patterns)

        # Update experience
        experience.compressed_pattern = compressed

        return compressed

    def get_stats(self) -> Dict:
        """
        Get statistics about stored experiences.

        Returns:
            Dictionary with statistics
        """
        self._ensure_loaded()

        if not self._experiences:
            return {
                'total_experiences': 0,
                'by_domain': {},
                'avg_confidence': 0,
                'total_retrievals': 0,
                'total_helpful': 0,
                'most_helpful': [],
                'most_retrieved': []
            }

        # Calculate statistics
        by_domain = {}
        total_confidence = 0
        total_retrievals = 0
        total_helpful = 0

        for exp in self._experiences.values():
            # Domain counts
            by_domain[exp.domain] = by_domain.get(exp.domain, 0) + 1

            # Totals
            total_confidence += exp.confidence
            total_retrievals += exp.retrieval_count
            total_helpful += exp.helpful_count

        # Sort by helpful and retrieval counts
        sorted_by_helpful = sorted(
            self._experiences.values(),
            key=lambda e: e.helpful_count,
            reverse=True
        )[:5]

        sorted_by_retrieved = sorted(
            self._experiences.values(),
            key=lambda e: e.retrieval_count,
            reverse=True
        )[:5]

        return {
            'total_experiences': len(self._experiences),
            'by_domain': by_domain,
            'avg_confidence': total_confidence / len(self._experiences),
            'total_retrievals': total_retrievals,
            'total_helpful': total_helpful,
            'most_helpful': [
                {'id': e.id, 'query': e.query[:50], 'helpful_count': e.helpful_count}
                for e in sorted_by_helpful if e.helpful_count > 0
            ],
            'most_retrieved': [
                {'id': e.id, 'query': e.query[:50], 'retrieval_count': e.retrieval_count}
                for e in sorted_by_retrieved if e.retrieval_count > 0
            ]
        }

    def list_all(
        self,
        domain: Optional[str] = None,
        limit: int = 100
    ) -> List[Experience]:
        """
        List all experiences, optionally filtered by domain.

        Args:
            domain: Filter by domain (optional)
            limit: Maximum number to return

        Returns:
            List of experiences sorted by timestamp (newest first)
        """
        self._ensure_loaded()

        experiences = list(self._experiences.values())

        # Filter by domain
        if domain:
            experiences = [e for e in experiences if e.domain == domain]

        # Sort by timestamp (newest first)
        experiences.sort(key=lambda e: e.timestamp, reverse=True)

        return experiences[:limit]

    def clear(self) -> int:
        """
        Clear all experiences.

        Returns:
            Number of experiences cleared
        """
        self._ensure_loaded()
        count = len(self._experiences)
        self._experiences = {}
        self._save()
        return count


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI entry point for experience memory."""
    parser = argparse.ArgumentParser(
        description='Experience Memory - CER Storage for Research Loop',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--storage', '-s',
        default=DEFAULT_STORAGE_PATH,
        help='Path to storage file'
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output as JSON'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Store command
    store_parser = subparsers.add_parser('store', help='Store a new experience')
    store_parser.add_argument('--query', '-q', required=True, help='Research query')
    store_parser.add_argument('--findings', '-f', required=True, help='Findings JSON')
    store_parser.add_argument('--synthesis', default='', help='Synthesis text')
    store_parser.add_argument('--domain', '-d', default='general', help='Domain (ai-ml, investment, general)')
    store_parser.add_argument('--confidence', '-c', type=int, default=50, help='Confidence score (0-100)')
    store_parser.add_argument('--sub-questions', help='Sub-questions JSON array')

    # Retrieve command
    retrieve_parser = subparsers.add_parser('retrieve', help='Retrieve similar experiences')
    retrieve_parser.add_argument('--query', '-q', required=True, help='Query to search for')
    retrieve_parser.add_argument('--domain', '-d', help='Filter by domain')
    retrieve_parser.add_argument('--k', '-k', type=int, default=5, help='Number of results')
    retrieve_parser.add_argument('--min-similarity', type=float, default=0.3, help='Minimum similarity')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get experience by ID')
    get_parser.add_argument('id', help='Experience ID')

    # Stats command
    subparsers.add_parser('stats', help='Get statistics')

    # List command
    list_parser = subparsers.add_parser('list', help='List experiences')
    list_parser.add_argument('--domain', '-d', help='Filter by domain')
    list_parser.add_argument('--limit', '-l', type=int, default=10, help='Limit results')

    # Mark helpful command
    helpful_parser = subparsers.add_parser('mark-helpful', help='Mark experience as helpful')
    helpful_parser.add_argument('id', help='Experience ID')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all experiences')
    clear_parser.add_argument('--confirm', action='store_true', required=True, help='Confirm clear')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    memory = ExperienceMemory(args.storage)

    def output(data: Any):
        """Output data in appropriate format."""
        if args.json:
            print(json.dumps(data, indent=2, default=str))
        else:
            if isinstance(data, dict):
                for k, v in data.items():
                    print(f"{k}: {v}")
            elif isinstance(data, list):
                for item in data:
                    print(item)
            else:
                print(data)

    # Execute command
    if args.command == 'store':
        # Parse findings
        try:
            findings = json.loads(args.findings)
            if not isinstance(findings, list):
                findings = [findings]
        except json.JSONDecodeError:
            findings = [{'content': args.findings}]

        # Parse sub-questions
        sub_questions = []
        if args.sub_questions:
            try:
                sub_questions = json.loads(args.sub_questions)
            except json.JSONDecodeError:
                sub_questions = [args.sub_questions]

        # Create experience
        experience = Experience(
            id='',  # Will be generated
            query=args.query,
            domain=args.domain,
            sub_questions=sub_questions,
            findings=findings,
            synthesis=args.synthesis,
            confidence=args.confidence
        )

        # Compress patterns
        memory.compress(experience)

        # Store
        exp_id = memory.store(experience)
        output({'id': exp_id, 'status': 'stored'})

    elif args.command == 'retrieve':
        results = memory.retrieve(
            query=args.query,
            domain=args.domain,
            k=args.k,
            min_similarity=args.min_similarity
        )

        if args.json:
            output([r.to_dict() for r in results])
        else:
            if not results:
                print("No similar experiences found")
            else:
                for i, r in enumerate(results, 1):
                    print(f"\n--- Result {i} (similarity: {r.similarity:.3f}) ---")
                    print(f"ID: {r.experience.id}")
                    print(f"Query: {r.experience.query}")
                    print(f"Domain: {r.experience.domain}")
                    print(f"Confidence: {r.experience.confidence}")
                    print(f"Pattern: {r.experience.compressed_pattern}")

    elif args.command == 'get':
        experience = memory.get(args.id)
        if experience:
            output(experience.to_dict())
        else:
            print(f"Experience not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'stats':
        stats = memory.get_stats()
        output(stats)

    elif args.command == 'list':
        experiences = memory.list_all(domain=args.domain, limit=args.limit)

        if args.json:
            output([e.to_dict() for e in experiences])
        else:
            if not experiences:
                print("No experiences found")
            else:
                for e in experiences:
                    print(f"{e.id} | {e.domain} | {e.query[:50]}... | conf: {e.confidence}")

    elif args.command == 'mark-helpful':
        if memory.mark_helpful(args.id):
            output({'id': args.id, 'status': 'marked_helpful'})
        else:
            print(f"Experience not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'clear':
        count = memory.clear()
        output({'cleared': count, 'status': 'cleared'})


if __name__ == '__main__':
    main()
