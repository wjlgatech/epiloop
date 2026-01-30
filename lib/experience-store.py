#!/usr/bin/env python3
# pylint: disable=broad-except
"""
experience-store.py - Domain-Contextualized Experience Store for claude-loop

Provides a scalable experience storage system using ChromaDB for vector similarity search.
Experiences are tagged with domain context so similar symptoms from different domains
aren't conflated.

Features:
- ChromaDB vector database (file-based, no server required)
- Sentence-transformers embeddings (all-MiniLM-L6-v2) with hash-based fallback
- Domain-aware storage with domain-prefixed embeddings
- Domain-partitioned collections for efficient filtering
- Retrieval with feedback tracking (helpful_count, retrieval_count)
- Per-domain LRU eviction when DB exceeds 500MB size limit
- Automatic DB creation on first use
- CLI interface for storing and querying experiences

Usage:
    # Store a new experience with domain context
    python3 lib/experience-store.py store "problem description" "solution approach" \\
        --domain '{"project_type": "unity", "language": "csharp", "frameworks": ["Unity XR"]}'

    # Store with additional context
    python3 lib/experience-store.py store "problem" "solution" \\
        --domain '{"project_type": "web_frontend"}' --context '{"category": "API"}'

    # Get experience statistics by domain
    python3 lib/experience-store.py stats --by-domain

    # List experiences filtered by domain
    python3 lib/experience-store.py list --limit 10 --domain-type unity

    # Search experiences (retrieval with domain filtering)
    python3 lib/experience-store.py search "UI element not found" --domain-type unity

    # Get experience by ID
    python3 lib/experience-store.py get <experience_id>

    # Update success/retrieval/helpful counts
    python3 lib/experience-store.py update-success <experience_id>
    python3 lib/experience-store.py update-retrieval <experience_id> --outcome helped

    # Clear all experiences
    python3 lib/experience-store.py clear --confirm

CLI Options:
    --db-dir DIR        Database directory (default: .claude-loop/experiences)
    --json              Output as JSON
    --verbose           Enable verbose output
"""

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import ChromaDB and sentence-transformers
CHROMADB_AVAILABLE = False
EMBEDDINGS_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Constants
# ============================================================================

DEFAULT_DB_DIR = ".claude-loop/experiences"
COLLECTION_NAME = "claude_loop_experiences"
MAX_DB_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2
HASH_EMBEDDING_DIM = 384  # Match sentence-transformer dimension for compatibility


# ============================================================================
# Data Classes
# ============================================================================

# Domain types supported by the system
DOMAIN_TYPES = [
    "web_frontend",
    "web_backend",
    "unity_game",
    "unity_xr",
    "isaac_sim",
    "ml_training",
    "ml_inference",
    "data_pipeline",
    "cli_tool",
    "robotics",
    "other",
]

# Parent categories for domain grouping
DOMAIN_PARENT_CATEGORIES = {
    "web_frontend": "web",
    "web_backend": "web",
    "unity_game": "unity",
    "unity_xr": "unity",
    "isaac_sim": "simulation",
    "ml_training": "ml",
    "ml_inference": "ml",
    "data_pipeline": "data",
    "cli_tool": "cli",
    "robotics": "physical",
    "other": "other",
}


@dataclass
class DomainContext:
    """Domain context for an experience entry.

    Captures project type, language, frameworks, and tools used.
    This enables domain-aware retrieval and prevents conflating
    similar symptoms from different domains.
    """
    project_type: str  # One of DOMAIN_TYPES
    language: str = ""  # e.g., "python", "csharp", "typescript"
    frameworks: List[str] = field(default_factory=list)  # e.g., ["Unity XR", "Isaac Sim"]
    tools_used: List[str] = field(default_factory=list)  # e.g., ["ros2", "nvidia-docker"]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'DomainContext':
        data.setdefault('project_type', 'other')
        data.setdefault('language', '')
        data.setdefault('frameworks', [])
        data.setdefault('tools_used', [])
        return cls(**data)

    def get_parent_category(self) -> str:
        """Get the parent category for this domain."""
        return DOMAIN_PARENT_CATEGORIES.get(self.project_type, "other")

    def to_embedding_prefix(self) -> str:
        """Generate embedding prefix for domain-aware embeddings.

        Example: '[unity:csharp:Unity XR]' or '[web:typescript]'
        """
        parts = [self.project_type]
        if self.language:
            parts.append(self.language)
        if self.frameworks:
            parts.append(self.frameworks[0])  # Primary framework
        return f"[{':'.join(parts)}]"


@dataclass
class ExperienceEntry:
    """Represents a stored experience entry with domain context.

    Tracks usage metrics including success, retrieval, and helpful counts
    to enable retrieval quality feedback loops.
    """
    id: str
    problem_signature: str
    solution_approach: str
    domain_context: DomainContext  # REQUIRED: Domain context for this experience
    context: Dict[str, Any]  # Additional context (category, tags, etc.)
    success_count: int  # Number of times solution was used successfully
    retrieval_count: int  # Number of times this experience was retrieved
    helpful_count: int  # Number of times marked as helpful after retrieval
    last_used: str  # ISO timestamp
    created_at: str  # ISO timestamp
    embedding_type: str  # "sentence_transformer" or "hash"
    category: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        # DomainContext is already serialized by asdict
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ExperienceEntry':
        # Handle missing fields with defaults
        data.setdefault('category', '')
        data.setdefault('tags', [])
        data.setdefault('retrieval_count', 0)
        data.setdefault('helpful_count', 0)

        # Handle domain_context
        if 'domain_context' in data:
            if isinstance(data['domain_context'], dict):
                data['domain_context'] = DomainContext.from_dict(data['domain_context'])
        else:
            # Legacy entries without domain context
            data['domain_context'] = DomainContext(project_type='other')

        return cls(**data)

    def get_helpful_rate(self) -> float:
        """Calculate the helpful rate (helpful_count / retrieval_count)."""
        if self.retrieval_count == 0:
            return 0.0
        return self.helpful_count / self.retrieval_count


@dataclass
class DomainStats:
    """Statistics for a single domain."""
    domain_type: str
    experience_count: int
    total_retrievals: int
    total_helpful: int
    helpful_rate: float
    avg_success_count: float
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExperienceStats:
    """Statistics about the experience store."""
    total_experiences: int
    total_size_bytes: int
    size_limit_bytes: int
    usage_percent: float
    categories: Dict[str, int]
    domains: Dict[str, DomainStats]  # Domain-level breakdown
    avg_success_count: float
    avg_helpful_rate: float
    oldest_entry: Optional[str]
    newest_entry: Optional[str]
    embedding_type: str

    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert DomainStats objects to dicts
        data['domains'] = {k: v.to_dict() if hasattr(v, 'to_dict') else v
                          for k, v in self.domains.items()}
        return data


# ============================================================================
# Embedding Functions
# ============================================================================

class EmbeddingProvider:
    """Provides embeddings using sentence-transformers or hash-based fallback.

    Supports domain-prefixed embeddings for domain-aware similarity search.
    Example: '[unity:csharp] UI element not found' produces embeddings
    that cluster with other Unity-related problems.
    """

    def __init__(self, use_sentence_transformers: bool = True):
        self.model = None
        self.use_sentence_transformers = use_sentence_transformers and EMBEDDINGS_AVAILABLE

        if self.use_sentence_transformers:
            try:
                self.model = SentenceTransformer(EMBEDDING_MODEL)
            except Exception as e:
                print(f"Warning: Failed to load sentence-transformer model: {e}", file=sys.stderr)
                print("Falling back to hash-based embeddings", file=sys.stderr)
                self.use_sentence_transformers = False

    def get_embedding(self, text: str, domain_context: Optional[DomainContext] = None) -> List[float]:
        """Get embedding for text with optional domain prefix.

        Args:
            text: The text to embed
            domain_context: Optional domain context for domain-prefixed embedding

        Returns:
            List of floats representing the embedding vector
        """
        # Prepend domain prefix if provided
        if domain_context:
            prefix = domain_context.to_embedding_prefix()
            text = f"{prefix} {text}"

        if self.use_sentence_transformers and self.model:
            return self.model.encode(text, convert_to_numpy=True).tolist()
        else:
            return self._hash_embedding(text)

    def _hash_embedding(self, text: str) -> List[float]:
        """Generate a deterministic hash-based embedding.

        This creates a pseudo-embedding from SHA256 hash that can be used
        for exact/near-exact matching when sentence-transformers unavailable.
        """
        # Create SHA256 hash
        hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()

        # Extend hash to fill embedding dimension
        extended_bytes = b''
        counter = 0
        while len(extended_bytes) < HASH_EMBEDDING_DIM * 4:  # 4 bytes per float
            extended_bytes += hashlib.sha256(hash_bytes + counter.to_bytes(4, 'big')).digest()
            counter += 1

        # Convert to floats in [-1, 1] range
        embedding = []
        for i in range(HASH_EMBEDDING_DIM):
            # Take 4 bytes and convert to unsigned int
            byte_chunk = extended_bytes[i*4:(i+1)*4]
            value = int.from_bytes(byte_chunk, 'big')
            # Normalize to [-1, 1]
            normalized = (value / (2**32 - 1)) * 2 - 1
            embedding.append(normalized)

        return embedding

    @property
    def embedding_type(self) -> str:
        """Get the type of embedding being used."""
        return "sentence_transformer" if self.use_sentence_transformers else "hash"


# ============================================================================
# Experience Store Class
# ============================================================================

class ExperienceStore:
    """
    Domain-contextualized experience store with vector database backend.

    Uses ChromaDB for persistent storage with domain-partitioned collections.
    Experiences are stored with domain context for domain-aware retrieval.
    Falls back to a JSON-based store if ChromaDB is unavailable.
    """

    def __init__(self, db_dir: str = DEFAULT_DB_DIR, use_embeddings: bool = True):
        """Initialize the experience store.

        Args:
            db_dir: Directory to store the database
            use_embeddings: Whether to use sentence-transformer embeddings
        """
        self.db_dir = Path(db_dir)
        self.chroma_dir = self.db_dir / "chroma_db"
        self.fallback_file = self.db_dir / "experiences_fallback.json"

        self.embedding_provider = EmbeddingProvider(use_embeddings)
        self.client = None
        self.collections: Dict[str, Any] = {}  # Domain-partitioned collections
        self.use_chromadb = CHROMADB_AVAILABLE

        self._ensure_db_dir()
        self._init_store()

    def _ensure_db_dir(self) -> None:
        """Create database directory if it doesn't exist."""
        self.db_dir.mkdir(parents=True, exist_ok=True)

    def _get_collection_name(self, domain_type: str) -> str:
        """Get collection name for a domain type."""
        # Use parent category for collection partitioning
        parent = DOMAIN_PARENT_CATEGORIES.get(domain_type, "other")
        return f"{COLLECTION_NAME}_{parent}"

    def _get_or_create_collection(self, domain_type: str) -> Any:
        """Get or create a domain-partitioned collection."""
        collection_name = self._get_collection_name(domain_type)

        if collection_name in self.collections:
            return self.collections[collection_name]

        if self.use_chromadb and self.client:
            try:
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                self.collections[collection_name] = collection
                return collection
            except Exception as e:
                print(f"Warning: Failed to create collection {collection_name}: {e}", file=sys.stderr)
                return None
        return None

    def _get_all_collections(self) -> List[Any]:
        """Get all domain-partitioned collections."""
        if not self.use_chromadb or not self.client:
            return []

        collections = []
        try:
            # Get all collections from ChromaDB
            all_collections = self.client.list_collections()
            for coll in all_collections:
                if coll.name.startswith(COLLECTION_NAME):
                    collections.append(coll)
                    self.collections[coll.name] = coll
        except Exception:
            pass
        return collections

    def _init_store(self) -> None:
        """Initialize the vector store."""
        if self.use_chromadb:
            try:
                self.client = chromadb.PersistentClient(
                    path=str(self.chroma_dir),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    )
                )
                # Load existing collections
                self._get_all_collections()
            except Exception as e:
                print(f"Warning: Failed to initialize ChromaDB: {e}", file=sys.stderr)
                print("Falling back to JSON storage", file=sys.stderr)
                self.use_chromadb = False
                self._init_fallback()
        else:
            self._init_fallback()

    def _init_fallback(self) -> None:
        """Initialize JSON fallback storage with domain partitioning."""
        # Structure: {"domains": {"web": {"experiences": {}, "embeddings": {}}, ...}}
        self.fallback_data = {"domains": {}}
        if self.fallback_file.exists():
            try:
                with open(self.fallback_file, 'r') as f:
                    loaded = json.load(f)
                    # Handle legacy format (flat structure)
                    if "experiences" in loaded and "domains" not in loaded:
                        # Migrate to domain structure
                        self.fallback_data = {"domains": {"other": loaded}}
                    else:
                        self.fallback_data = loaded
            except (json.JSONDecodeError, IOError):
                pass

    def _get_domain_data(self, domain_type: str) -> Dict[str, Any]:
        """Get or create domain data in fallback storage."""
        parent = DOMAIN_PARENT_CATEGORIES.get(domain_type, "other")
        if parent not in self.fallback_data["domains"]:
            self.fallback_data["domains"][parent] = {"experiences": {}, "embeddings": {}}
        return self.fallback_data["domains"][parent]

    def _save_fallback(self) -> None:
        """Save fallback data to disk."""
        with open(self.fallback_file, 'w') as f:
            json.dump(self.fallback_data, f, indent=2)

    def _generate_id(self, problem: str, solution: str) -> str:
        """Generate a unique ID for an experience."""
        content = f"{problem}:{solution}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_db_size(self, domain_type: Optional[str] = None) -> int:
        """Get database size in bytes, optionally for a specific domain.

        Args:
            domain_type: Optional domain type to get size for. If None, returns total size.
        """
        total_size = 0

        if self.use_chromadb and self.chroma_dir.exists():
            for file_path in self.chroma_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        elif self.fallback_file.exists():
            if domain_type:
                # Estimate size for specific domain
                parent = DOMAIN_PARENT_CATEGORIES.get(domain_type, "other")
                domain_data = self.fallback_data.get("domains", {}).get(parent, {})
                total_size = len(json.dumps(domain_data).encode())
            else:
                total_size = self.fallback_file.stat().st_size

        return total_size

    def _check_and_evict(self) -> int:
        """Check size and evict LRU entries per domain if needed.

        Uses per-domain LRU eviction to maintain fairness across domains.

        Returns:
            Number of entries evicted
        """
        evicted = 0
        current_size = self._get_db_size()

        if current_size <= MAX_DB_SIZE_BYTES:
            return 0

        # Get experiences grouped by domain
        all_experiences = self._get_all_experiences()
        domain_experiences: Dict[str, List[ExperienceEntry]] = {}
        for exp in all_experiences:
            domain = exp.domain_context.project_type
            if domain not in domain_experiences:
                domain_experiences[domain] = []
            domain_experiences[domain].append(exp)

        # Sort each domain's experiences by last_used (oldest first)
        for domain in domain_experiences:
            domain_experiences[domain].sort(key=lambda x: x.last_used)

        # Evict until under limit (with 10% buffer)
        # Use round-robin per-domain eviction
        target_size = int(MAX_DB_SIZE_BYTES * 0.9)
        domains_with_entries = [d for d in domain_experiences if domain_experiences[d]]

        while current_size > target_size and domains_with_entries:
            for domain in list(domains_with_entries):
                if domain_experiences[domain]:
                    oldest = domain_experiences[domain].pop(0)
                    self._delete_experience(oldest.id, oldest.domain_context.project_type)
                    evicted += 1
                    current_size = self._get_db_size()

                    if current_size <= target_size:
                        break

                    if not domain_experiences[domain]:
                        domains_with_entries.remove(domain)
                else:
                    if domain in domains_with_entries:
                        domains_with_entries.remove(domain)

        return evicted

    def _get_all_experiences(self, domain_type: Optional[str] = None) -> List[ExperienceEntry]:
        """Get all experiences, optionally filtered by domain.

        Args:
            domain_type: Optional domain type to filter by. If None, returns all.
        """
        experiences = []

        if self.use_chromadb:
            try:
                # Get from all collections or specific domain collection
                if domain_type:
                    collection = self._get_or_create_collection(domain_type)
                    if collection:
                        results = collection.get()
                        experiences.extend(self._parse_chromadb_results(results))
                else:
                    for collection in self._get_all_collections():
                        results = collection.get()
                        experiences.extend(self._parse_chromadb_results(results))
            except Exception:
                pass
        else:
            # Get from fallback storage
            if domain_type:
                domain_data = self._get_domain_data(domain_type)
                for exp_id, exp_data in domain_data.get('experiences', {}).items():
                    exp_data = dict(exp_data)  # Copy to avoid modifying original
                    exp_data['id'] = exp_id
                    experiences.append(ExperienceEntry.from_dict(exp_data))
            else:
                for domain_data in self.fallback_data.get("domains", {}).values():
                    for exp_id, exp_data in domain_data.get('experiences', {}).items():
                        exp_data = dict(exp_data)
                        exp_data['id'] = exp_id
                        experiences.append(ExperienceEntry.from_dict(exp_data))

        return experiences

    def _parse_chromadb_results(self, results: dict) -> List[ExperienceEntry]:
        """Parse ChromaDB query results into ExperienceEntry objects."""
        experiences = []
        if not results or not results.get('ids'):
            return experiences

        for i, exp_id in enumerate(results['ids']):
            metadata = results['metadatas'][i] if results.get('metadatas') else {}

            # Parse domain context from metadata
            domain_context_data = json.loads(metadata.get('domain_context', '{}'))
            domain_context = DomainContext.from_dict(domain_context_data) if domain_context_data else DomainContext(project_type='other')

            experiences.append(ExperienceEntry(
                id=exp_id,
                problem_signature=metadata.get('problem_signature', ''),
                solution_approach=metadata.get('solution_approach', ''),
                domain_context=domain_context,
                context=json.loads(metadata.get('context', '{}')),
                success_count=int(metadata.get('success_count', 0)),
                retrieval_count=int(metadata.get('retrieval_count', 0)),
                helpful_count=int(metadata.get('helpful_count', 0)),
                last_used=metadata.get('last_used', ''),
                created_at=metadata.get('created_at', ''),
                embedding_type=metadata.get('embedding_type', 'unknown'),
                category=metadata.get('category', ''),
                tags=json.loads(metadata.get('tags', '[]')),
            ))
        return experiences

    def _delete_experience(self, exp_id: str, domain_type: Optional[str] = None) -> bool:
        """Delete an experience by ID.

        Args:
            exp_id: Experience ID to delete
            domain_type: Domain type to search in. If None, searches all domains.
        """
        if self.use_chromadb:
            try:
                # Try to delete from specific collection or search all
                if domain_type:
                    collection = self._get_or_create_collection(domain_type)
                    if collection:
                        collection.delete(ids=[exp_id])
                        return True
                else:
                    # Search all collections
                    for collection in self._get_all_collections():
                        try:
                            collection.delete(ids=[exp_id])
                            return True
                        except Exception:
                            continue
                return False
            except Exception:
                return False
        else:
            # Search in specific domain or all domains
            if domain_type:
                domain_data = self._get_domain_data(domain_type)
                if exp_id in domain_data.get('experiences', {}):
                    del domain_data['experiences'][exp_id]
                    if exp_id in domain_data.get('embeddings', {}):
                        del domain_data['embeddings'][exp_id]
                    self._save_fallback()
                    return True
            else:
                # Search all domains
                for domain_data in self.fallback_data.get("domains", {}).values():
                    if exp_id in domain_data.get('experiences', {}):
                        del domain_data['experiences'][exp_id]
                        if exp_id in domain_data.get('embeddings', {}):
                            del domain_data['embeddings'][exp_id]
                        self._save_fallback()
                        return True
            return False

    def record_experience(
        self,
        problem: str,
        solution: str,
        domain_context: Optional[DomainContext] = None,
        context: Optional[Dict[str, Any]] = None,
        category: str = "",
        tags: Optional[List[str]] = None,
    ) -> Tuple[str, bool]:
        """Record a new experience with domain context.

        Args:
            problem: Problem description/signature
            solution: Solution approach
            domain_context: Domain context for domain-aware storage
            context: Additional context (JSON-serializable dict)
            category: Category for the experience
            tags: Tags for categorization

        Returns:
            Tuple of (experience_id, success)
        """
        context = context or {}
        tags = tags or []
        domain_context = domain_context or DomainContext(project_type='other')

        # Generate ID and timestamps
        exp_id = self._generate_id(problem, solution)
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Generate embedding with domain prefix
        combined_text = f"{problem}\n{solution}"
        embedding = self.embedding_provider.get_embedding(combined_text, domain_context)

        # Create entry
        entry = ExperienceEntry(
            id=exp_id,
            problem_signature=problem,
            solution_approach=solution,
            domain_context=domain_context,
            context=context,
            success_count=1,
            retrieval_count=0,
            helpful_count=0,
            last_used=now,
            created_at=now,
            embedding_type=self.embedding_provider.embedding_type,
            category=category,
            tags=tags,
        )

        # Store in domain-partitioned collection
        if self.use_chromadb:
            try:
                collection = self._get_or_create_collection(domain_context.project_type)
                if not collection:
                    return exp_id, False

                metadata = {
                    'problem_signature': problem,
                    'solution_approach': solution,
                    'domain_context': json.dumps(domain_context.to_dict()),
                    'context': json.dumps(context),
                    'success_count': str(entry.success_count),
                    'retrieval_count': str(entry.retrieval_count),
                    'helpful_count': str(entry.helpful_count),
                    'last_used': entry.last_used,
                    'created_at': entry.created_at,
                    'embedding_type': entry.embedding_type,
                    'category': category,
                    'tags': json.dumps(tags),
                }

                collection.add(
                    ids=[exp_id],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[combined_text],
                )
            except Exception as e:
                print(f"Error storing experience: {e}", file=sys.stderr)
                return exp_id, False
        else:
            # Store in domain-partitioned fallback storage
            domain_data = self._get_domain_data(domain_context.project_type)
            domain_data['experiences'][exp_id] = entry.to_dict()
            domain_data['embeddings'][exp_id] = embedding
            self._save_fallback()

        # Check and evict if needed
        self._check_and_evict()

        return exp_id, True

    def get_experience(self, exp_id: str, domain_type: Optional[str] = None) -> Optional[ExperienceEntry]:
        """Get an experience by ID.

        Args:
            exp_id: Experience ID
            domain_type: Optional domain type to search in

        Returns:
            ExperienceEntry or None if not found
        """
        if self.use_chromadb:
            try:
                # Search in specific domain or all domains
                if domain_type:
                    collection = self._get_or_create_collection(domain_type)
                    if collection:
                        results = collection.get(ids=[exp_id])
                        parsed = self._parse_chromadb_results(results)
                        if parsed:
                            return parsed[0]
                else:
                    # Search all collections
                    for collection in self._get_all_collections():
                        try:
                            results = collection.get(ids=[exp_id])
                            parsed = self._parse_chromadb_results(results)
                            if parsed:
                                return parsed[0]
                        except Exception:
                            continue
            except Exception:
                pass
            return None
        else:
            # Search in fallback storage
            if domain_type:
                domain_data = self._get_domain_data(domain_type)
                exp_data = domain_data.get('experiences', {}).get(exp_id)
                if exp_data:
                    exp_data = dict(exp_data)
                    exp_data['id'] = exp_id
                    return ExperienceEntry.from_dict(exp_data)
            else:
                # Search all domains
                for domain_data in self.fallback_data.get("domains", {}).values():
                    exp_data = domain_data.get('experiences', {}).get(exp_id)
                    if exp_data:
                        exp_data = dict(exp_data)
                        exp_data['id'] = exp_id
                        return ExperienceEntry.from_dict(exp_data)
            return None

    def _update_experience_metadata(self, entry: ExperienceEntry, updates: Dict[str, Any]) -> bool:
        """Update metadata for an experience.

        Args:
            entry: The experience entry to update
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        if self.use_chromadb:
            try:
                collection = self._get_or_create_collection(entry.domain_context.project_type)
                if not collection:
                    return False

                metadata = {
                    'problem_signature': entry.problem_signature,
                    'solution_approach': entry.solution_approach,
                    'domain_context': json.dumps(entry.domain_context.to_dict()),
                    'context': json.dumps(entry.context),
                    'success_count': str(updates.get('success_count', entry.success_count)),
                    'retrieval_count': str(updates.get('retrieval_count', entry.retrieval_count)),
                    'helpful_count': str(updates.get('helpful_count', entry.helpful_count)),
                    'last_used': updates.get('last_used', entry.last_used),
                    'created_at': entry.created_at,
                    'embedding_type': entry.embedding_type,
                    'category': entry.category,
                    'tags': json.dumps(entry.tags),
                }

                collection.update(ids=[entry.id], metadatas=[metadata])
                return True
            except Exception:
                return False
        else:
            domain_data = self._get_domain_data(entry.domain_context.project_type)
            if entry.id in domain_data.get('experiences', {}):
                for key, value in updates.items():
                    domain_data['experiences'][entry.id][key] = value
                self._save_fallback()
                return True
            return False

    def update_success_count(self, exp_id: str, increment: int = 1) -> bool:
        """Update the success count for an experience.

        Args:
            exp_id: Experience ID
            increment: Amount to increment (default 1)

        Returns:
            True if successful, False otherwise
        """
        entry = self.get_experience(exp_id)
        if not entry:
            return False

        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return self._update_experience_metadata(entry, {
            'success_count': entry.success_count + increment,
            'last_used': now,
        })

    def update_retrieval_outcome(
        self,
        exp_id: str,
        outcome: str,  # 'used', 'ignored', 'helped', 'hurt'
    ) -> bool:
        """Update retrieval outcome for an experience.

        This method tracks retrieval quality by recording whether retrieved
        experiences were helpful.

        Args:
            exp_id: Experience ID
            outcome: One of 'used', 'ignored', 'helped', 'hurt'

        Returns:
            True if successful, False otherwise
        """
        entry = self.get_experience(exp_id)
        if not entry:
            return False

        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        updates: Dict[str, Any] = {'last_used': now}

        # Increment retrieval count for all outcomes except 'ignored'
        if outcome != 'ignored':
            updates['retrieval_count'] = entry.retrieval_count + 1

        # Increment helpful count if the experience helped
        if outcome == 'helped':
            updates['helpful_count'] = entry.helpful_count + 1

        return self._update_experience_metadata(entry, updates)

    def list_experiences(
        self,
        limit: int = 100,
        domain_type: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = "last_used",
    ) -> List[ExperienceEntry]:
        """List experiences with optional filtering by domain.

        Args:
            limit: Maximum number of experiences to return
            domain_type: Filter by domain type (optional)
            category: Filter by category (optional)
            sort_by: Sort field ("last_used", "success_count", "created_at", "helpful_rate")

        Returns:
            List of ExperienceEntry objects
        """
        all_experiences = self._get_all_experiences(domain_type)

        # Filter by category if specified
        if category:
            all_experiences = [e for e in all_experiences if e.category == category]

        # Sort
        if sort_by == "success_count":
            all_experiences.sort(key=lambda x: x.success_count, reverse=True)
        elif sort_by == "created_at":
            all_experiences.sort(key=lambda x: x.created_at, reverse=True)
        elif sort_by == "helpful_rate":
            all_experiences.sort(key=lambda x: x.get_helpful_rate(), reverse=True)
        else:  # default: last_used
            all_experiences.sort(key=lambda x: x.last_used, reverse=True)

        return all_experiences[:limit]

    def get_stats(self, by_domain: bool = False) -> ExperienceStats:
        """Get statistics about the experience store.

        Args:
            by_domain: Include per-domain breakdown

        Returns:
            ExperienceStats object with domain breakdown
        """
        all_experiences = self._get_all_experiences()
        total = len(all_experiences)

        # Calculate category distribution and domain stats
        categories: Dict[str, int] = {}
        domain_data: Dict[str, Dict[str, Any]] = {}  # domain -> {count, success, retrievals, helpful}
        total_success = 0
        helpful_count_total = 0
        retrieval_count_total = 0
        oldest = None
        newest = None

        for exp in all_experiences:
            cat = exp.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1
            total_success += exp.success_count
            helpful_count_total += exp.helpful_count
            retrieval_count_total += exp.retrieval_count

            # Domain stats
            domain = exp.domain_context.project_type
            if domain not in domain_data:
                domain_data[domain] = {
                    'count': 0,
                    'success': 0,
                    'retrievals': 0,
                    'helpful': 0,
                }
            domain_data[domain]['count'] += 1
            domain_data[domain]['success'] += exp.success_count
            domain_data[domain]['retrievals'] += exp.retrieval_count
            domain_data[domain]['helpful'] += exp.helpful_count

            if oldest is None or exp.created_at < oldest:
                oldest = exp.created_at
            if newest is None or exp.created_at > newest:
                newest = exp.created_at

        avg_success = total_success / total if total > 0 else 0.0
        avg_helpful_rate = helpful_count_total / retrieval_count_total if retrieval_count_total > 0 else 0.0
        db_size = self._get_db_size()
        usage_percent = (db_size / MAX_DB_SIZE_BYTES) * 100 if MAX_DB_SIZE_BYTES > 0 else 0.0

        # Build domain stats
        domains: Dict[str, DomainStats] = {}
        if by_domain:
            for domain, data in domain_data.items():
                helpful_rate = data['helpful'] / data['retrievals'] if data['retrievals'] > 0 else 0.0
                avg_domain_success = data['success'] / data['count'] if data['count'] > 0 else 0.0
                domains[domain] = DomainStats(
                    domain_type=domain,
                    experience_count=data['count'],
                    total_retrievals=data['retrievals'],
                    total_helpful=data['helpful'],
                    helpful_rate=round(helpful_rate, 4),
                    avg_success_count=round(avg_domain_success, 2),
                    size_bytes=self._get_db_size(domain),
                )

        return ExperienceStats(
            total_experiences=total,
            total_size_bytes=db_size,
            size_limit_bytes=MAX_DB_SIZE_BYTES,
            usage_percent=round(usage_percent, 2),
            categories=categories,
            domains=domains,
            avg_success_count=round(avg_success, 2),
            avg_helpful_rate=round(avg_helpful_rate, 4),
            oldest_entry=oldest,
            newest_entry=newest,
            embedding_type=self.embedding_provider.embedding_type,
        )

    def search_similar(
        self,
        problem: str,
        domain_context: Optional[DomainContext] = None,
        k: int = 5,
        similarity_threshold: float = 0.75,
    ) -> List[Tuple[ExperienceEntry, float]]:
        """Search for similar experiences with domain filtering.

        Filters by domain first, then by embedding similarity.

        Args:
            problem: Problem description to search for
            domain_context: Domain context for filtering
            k: Maximum number of results to return
            similarity_threshold: Minimum cosine similarity (default 0.75)

        Returns:
            List of (ExperienceEntry, similarity_score) tuples
        """
        results: List[Tuple[ExperienceEntry, float]] = []

        # Generate query embedding with domain prefix
        embedding = self.embedding_provider.get_embedding(problem, domain_context)

        if self.use_chromadb:
            try:
                # Query the domain-specific collection
                if domain_context:
                    collection = self._get_or_create_collection(domain_context.project_type)
                    if collection:
                        query_results = collection.query(
                            query_embeddings=[embedding],
                            n_results=k * 2,  # Fetch more to filter by threshold
                        )
                        results.extend(self._process_query_results(query_results, similarity_threshold))

                    # Also check parent category collection if different
                    parent = domain_context.get_parent_category()
                    for collection in self._get_all_collections():
                        if collection.name == self._get_collection_name(domain_context.project_type):
                            continue  # Already searched
                        if parent in collection.name:
                            query_results = collection.query(
                                query_embeddings=[embedding],
                                n_results=k,
                            )
                            results.extend(self._process_query_results(query_results, similarity_threshold))
                else:
                    # Search all collections
                    for collection in self._get_all_collections():
                        query_results = collection.query(
                            query_embeddings=[embedding],
                            n_results=k,
                        )
                        results.extend(self._process_query_results(query_results, similarity_threshold))

            except Exception as e:
                print(f"Search error: {e}", file=sys.stderr)
        else:
            # Fallback: compute cosine similarity manually
            results = self._fallback_similarity_search(embedding, domain_context, k, similarity_threshold)

        # Sort by similarity and return top k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def _process_query_results(
        self,
        query_results: dict,
        threshold: float,
    ) -> List[Tuple[ExperienceEntry, float]]:
        """Process ChromaDB query results into entry/score tuples."""
        results = []
        if not query_results or not query_results.get('ids'):
            return results

        for i, exp_id in enumerate(query_results['ids'][0]):
            # ChromaDB returns distances, convert to similarity
            distance = query_results['distances'][0][i] if query_results.get('distances') else 0
            # For cosine distance, similarity = 1 - distance
            similarity = 1 - distance

            if similarity >= threshold:
                metadata = query_results['metadatas'][0][i] if query_results.get('metadatas') else {}
                domain_context_data = json.loads(metadata.get('domain_context', '{}'))
                domain_context = DomainContext.from_dict(domain_context_data) if domain_context_data else DomainContext(project_type='other')

                entry = ExperienceEntry(
                    id=exp_id,
                    problem_signature=metadata.get('problem_signature', ''),
                    solution_approach=metadata.get('solution_approach', ''),
                    domain_context=domain_context,
                    context=json.loads(metadata.get('context', '{}')),
                    success_count=int(metadata.get('success_count', 0)),
                    retrieval_count=int(metadata.get('retrieval_count', 0)),
                    helpful_count=int(metadata.get('helpful_count', 0)),
                    last_used=metadata.get('last_used', ''),
                    created_at=metadata.get('created_at', ''),
                    embedding_type=metadata.get('embedding_type', 'unknown'),
                    category=metadata.get('category', ''),
                    tags=json.loads(metadata.get('tags', '[]')),
                )
                results.append((entry, similarity))

        return results

    def _fallback_similarity_search(
        self,
        query_embedding: List[float],
        domain_context: Optional[DomainContext],
        _k: int,  # Unused, filtering done by threshold
        threshold: float,
    ) -> List[Tuple[ExperienceEntry, float]]:
        """Perform similarity search in fallback storage."""
        results = []

        # Get experiences and embeddings filtered by domain
        if domain_context:
            domain_data = self._get_domain_data(domain_context.project_type)
            experiences_data = domain_data.get('experiences', {})
            embeddings_data = domain_data.get('embeddings', {})
        else:
            experiences_data = {}
            embeddings_data = {}
            for domain_data in self.fallback_data.get("domains", {}).values():
                experiences_data.update(domain_data.get('experiences', {}))
                embeddings_data.update(domain_data.get('embeddings', {}))

        for exp_id, exp_data in experiences_data.items():
            if exp_id not in embeddings_data:
                continue

            stored_embedding = embeddings_data[exp_id]
            similarity = self._cosine_similarity(query_embedding, stored_embedding)

            if similarity >= threshold:
                exp_data = dict(exp_data)
                exp_data['id'] = exp_id
                entry = ExperienceEntry.from_dict(exp_data)
                results.append((entry, similarity))

        return results

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def clear(self, confirm: bool = False, domain_type: Optional[str] = None) -> int:
        """Clear experiences, optionally for a specific domain only.

        Args:
            confirm: Must be True to actually clear
            domain_type: Optional domain to clear (clears all if None)

        Returns:
            Number of experiences cleared
        """
        if not confirm:
            return 0

        count = len(self._get_all_experiences(domain_type))

        if self.use_chromadb:
            try:
                if domain_type:
                    # Clear specific domain collection
                    collection_name = self._get_collection_name(domain_type)
                    if collection_name in self.collections:
                        self.client.delete_collection(collection_name)
                        del self.collections[collection_name]
                else:
                    # Clear all domain collections
                    for collection in self._get_all_collections():
                        self.client.delete_collection(collection.name)
                    self.collections = {}
            except Exception:
                pass
        else:
            if domain_type:
                parent = DOMAIN_PARENT_CATEGORIES.get(domain_type, "other")
                if parent in self.fallback_data.get("domains", {}):
                    self.fallback_data["domains"][parent] = {"experiences": {}, "embeddings": {}}
            else:
                self.fallback_data = {"domains": {}}
            self._save_fallback()

        return count

    def get_categories(self) -> List[str]:
        """Get all unique categories.

        Returns:
            List of category names
        """
        all_experiences = self._get_all_experiences()
        categories = set()
        for exp in all_experiences:
            if exp.category:
                categories.add(exp.category)
        return sorted(list(categories))

    def get_domains(self) -> List[str]:
        """Get all domains that have experiences.

        Returns:
            List of domain types
        """
        all_experiences = self._get_all_experiences()
        domains = set()
        for exp in all_experiences:
            domains.add(exp.domain_context.project_type)
        return sorted(list(domains))


# ============================================================================
# CLI Interface
# ============================================================================

def _parse_domain_context(args: argparse.Namespace) -> Optional[DomainContext]:
    """Parse domain context from CLI arguments."""
    if hasattr(args, 'domain') and args.domain:
        try:
            domain_data = json.loads(args.domain)
            return DomainContext.from_dict(domain_data)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --domain", file=sys.stderr)
            return None
    elif hasattr(args, 'domain_type') and args.domain_type:
        return DomainContext(project_type=args.domain_type)
    return None


def cmd_store(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Store a new experience with domain context."""
    problem = args.problem
    solution = args.solution

    # Parse domain context
    domain_context = _parse_domain_context(args)

    # Parse additional context if provided
    context = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --context", file=sys.stderr)
            return 1

    # Parse tags if provided
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(',')]

    exp_id, success = store.record_experience(
        problem=problem,
        solution=solution,
        domain_context=domain_context,
        context=context,
        category=args.category or "",
        tags=tags,
    )

    if args.json:
        result = {
            "success": success,
            "experience_id": exp_id,
            "problem": problem[:100] + "..." if len(problem) > 100 else problem,
            "domain": domain_context.to_dict() if domain_context else None,
            "embedding_type": store.embedding_provider.embedding_type,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Experience stored: {exp_id}")
            if args.verbose:
                print(f"  Problem: {problem[:80]}...")
                print(f"  Solution: {solution[:80]}...")
                if domain_context:
                    print(f"  Domain: {domain_context.project_type}")
                print(f"  Embedding: {store.embedding_provider.embedding_type}")
        else:
            print(f"Failed to store experience", file=sys.stderr)
            return 1

    return 0


def cmd_stats(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Show experience store statistics with optional domain breakdown."""
    by_domain = getattr(args, 'by_domain', False)
    stats = store.get_stats(by_domain=by_domain)

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2))
    else:
        print("Experience Store Statistics:")
        print(f"  Total experiences:  {stats.total_experiences}")
        print(f"  Database size:      {stats.total_size_bytes:,} bytes")
        print(f"  Size limit:         {stats.size_limit_bytes:,} bytes")
        print(f"  Usage:              {stats.usage_percent}%")
        print(f"  Avg success count:  {stats.avg_success_count}")
        print(f"  Avg helpful rate:   {stats.avg_helpful_rate:.2%}")
        print(f"  Embedding type:     {stats.embedding_type}")

        if stats.oldest_entry:
            print(f"  Oldest entry:       {stats.oldest_entry}")
        if stats.newest_entry:
            print(f"  Newest entry:       {stats.newest_entry}")

        if stats.categories:
            print("\n  Categories:")
            for cat, count in sorted(stats.categories.items()):
                print(f"    {cat}: {count}")

        if by_domain and stats.domains:
            print("\n  Domain Breakdown:")
            for domain, domain_stats in sorted(stats.domains.items()):
                print(f"\n    [{domain}]")
                print(f"      Experiences:   {domain_stats.experience_count}")
                print(f"      Retrievals:    {domain_stats.total_retrievals}")
                print(f"      Helpful:       {domain_stats.total_helpful}")
                print(f"      Helpful rate:  {domain_stats.helpful_rate:.2%}")
                print(f"      Avg success:   {domain_stats.avg_success_count}")

    return 0


def cmd_list(args: argparse.Namespace, store: ExperienceStore) -> int:
    """List experiences with optional domain filtering."""
    domain_type = getattr(args, 'domain_type', None)
    experiences = store.list_experiences(
        limit=args.limit,
        domain_type=domain_type,
        category=args.category,
        sort_by=args.sort_by,
    )

    if args.json:
        result = {
            "count": len(experiences),
            "experiences": [e.to_dict() for e in experiences],
        }
        print(json.dumps(result, indent=2))
    else:
        if not experiences:
            print("No experiences found")
            return 0

        print(f"Experiences ({len(experiences)}):")
        for exp in experiences:
            problem_preview = exp.problem_signature[:50] + "..." if len(exp.problem_signature) > 50 else exp.problem_signature
            print(f"\n  [{exp.id}]")
            print(f"    Domain:    {exp.domain_context.project_type}")
            print(f"    Problem:   {problem_preview}")
            print(f"    Success:   {exp.success_count}")
            print(f"    Helpful:   {exp.helpful_count}/{exp.retrieval_count} ({exp.get_helpful_rate():.0%})")
            print(f"    Category:  {exp.category or 'uncategorized'}")
            print(f"    Last used: {exp.last_used}")

    return 0


def cmd_search(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Search for similar experiences with domain filtering."""
    domain_context = _parse_domain_context(args)

    results = store.search_similar(
        problem=args.query,
        domain_context=domain_context,
        k=args.limit,
        similarity_threshold=args.threshold,
    )

    if args.json:
        output = {
            "count": len(results),
            "results": [
                {"experience": e.to_dict(), "similarity": s}
                for e, s in results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        if not results:
            print("No similar experiences found")
            return 0

        print(f"Similar Experiences ({len(results)}):")
        for exp, similarity in results:
            problem_preview = exp.problem_signature[:50] + "..." if len(exp.problem_signature) > 50 else exp.problem_signature
            print(f"\n  [{exp.id}] (similarity: {similarity:.2%})")
            print(f"    Domain:   {exp.domain_context.project_type}")
            print(f"    Problem:  {problem_preview}")
            print(f"    Solution: {exp.solution_approach[:60]}...")
            print(f"    Helpful:  {exp.helpful_count}/{exp.retrieval_count}")

    return 0


def cmd_get(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Get experience by ID."""
    exp = store.get_experience(args.experience_id)

    if not exp:
        if args.json:
            print(json.dumps({"error": "Experience not found"}, indent=2))
        else:
            print(f"Experience not found: {args.experience_id}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(exp.to_dict(), indent=2))
    else:
        print(f"Experience [{exp.id}]:")
        print(f"  Domain:           {exp.domain_context.project_type}")
        if exp.domain_context.language:
            print(f"  Language:         {exp.domain_context.language}")
        if exp.domain_context.frameworks:
            print(f"  Frameworks:       {', '.join(exp.domain_context.frameworks)}")
        print(f"  Problem:          {exp.problem_signature}")
        print(f"  Solution:         {exp.solution_approach}")
        print(f"  Context:          {json.dumps(exp.context)}")
        print(f"  Success count:    {exp.success_count}")
        print(f"  Retrieval count:  {exp.retrieval_count}")
        print(f"  Helpful count:    {exp.helpful_count}")
        print(f"  Helpful rate:     {exp.get_helpful_rate():.2%}")
        print(f"  Category:         {exp.category or 'uncategorized'}")
        print(f"  Tags:             {', '.join(exp.tags) if exp.tags else 'none'}")
        print(f"  Embedding type:   {exp.embedding_type}")
        print(f"  Created at:       {exp.created_at}")
        print(f"  Last used:        {exp.last_used}")

    return 0


def cmd_update_success(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Update success count for an experience."""
    success = store.update_success_count(args.experience_id, args.increment)

    if args.json:
        result = {
            "success": success,
            "experience_id": args.experience_id,
            "increment": args.increment,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Updated success count for {args.experience_id} (+{args.increment})")
        else:
            print(f"Failed to update: experience not found", file=sys.stderr)
            return 1

    return 0


def cmd_feedback(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Record retrieval feedback for an experience."""
    success = store.update_retrieval_outcome(args.experience_id, args.outcome)

    if args.json:
        result = {
            "success": success,
            "experience_id": args.experience_id,
            "outcome": args.outcome,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Recorded feedback '{args.outcome}' for {args.experience_id}")
        else:
            print(f"Failed to record feedback: experience not found", file=sys.stderr)
            return 1

    return 0


def cmd_clear(args: argparse.Namespace, store: ExperienceStore) -> int:
    """Clear experiences, optionally for a specific domain."""
    if not args.confirm:
        print("Error: Use --confirm to actually clear experiences", file=sys.stderr)
        return 1

    domain_type = getattr(args, 'domain_type', None)
    count = store.clear(confirm=True, domain_type=domain_type)

    if args.json:
        result = {"cleared": count, "domain": domain_type}
        print(json.dumps(result, indent=2))
    else:
        if domain_type:
            print(f"Cleared {count} experiences from domain '{domain_type}'")
        else:
            print(f"Cleared {count} experiences")

    return 0


def cmd_categories(args: argparse.Namespace, store: ExperienceStore) -> int:
    """List all categories."""
    categories = store.get_categories()

    if args.json:
        print(json.dumps({"categories": categories}, indent=2))
    else:
        if categories:
            print("Categories:")
            for cat in categories:
                print(f"  - {cat}")
        else:
            print("No categories found")

    return 0


def cmd_domains(args: argparse.Namespace, store: ExperienceStore) -> int:
    """List all domains with experiences."""
    domains = store.get_domains()

    if args.json:
        print(json.dumps({"domains": domains}, indent=2))
    else:
        if domains:
            print("Domains:")
            for domain in domains:
                print(f"  - {domain}")
        else:
            print("No domains found")

    return 0


def create_parser():
    """Create argument parser."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"Database directory (default: {DEFAULT_DB_DIR})",
    )
    parent_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parent_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parent_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Use hash-based embeddings (skip sentence-transformers)",
    )

    # Main parser
    parser = argparse.ArgumentParser(
        description="Domain-Contextualized Experience Store for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # store command
    store_parser = subparsers.add_parser(
        "store", help="Store a new experience with domain context", parents=[parent_parser]
    )
    store_parser.add_argument("problem", help="Problem description")
    store_parser.add_argument("solution", help="Solution approach")
    store_parser.add_argument(
        "--domain", "-d",
        help="Domain context as JSON (e.g., '{\"project_type\": \"unity\", \"language\": \"csharp\"}')",
    )
    store_parser.add_argument(
        "--context", "-c",
        help="Additional context as JSON string",
    )
    store_parser.add_argument(
        "--category",
        help="Category for the experience",
    )
    store_parser.add_argument(
        "--tags", "-t",
        help="Comma-separated tags",
    )

    # stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Show experience store statistics", parents=[parent_parser]
    )
    stats_parser.add_argument(
        "--by-domain",
        action="store_true",
        help="Show breakdown by domain",
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List experiences with optional domain filtering", parents=[parent_parser]
    )
    list_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum number of experiences to return (default: 100)",
    )
    list_parser.add_argument(
        "--domain-type",
        choices=DOMAIN_TYPES,
        help="Filter by domain type",
    )
    list_parser.add_argument(
        "--category",
        help="Filter by category",
    )
    list_parser.add_argument(
        "--sort-by",
        choices=["last_used", "success_count", "created_at", "helpful_rate"],
        default="last_used",
        help="Sort field (default: last_used)",
    )

    # search command
    search_parser = subparsers.add_parser(
        "search", help="Search for similar experiences", parents=[parent_parser]
    )
    search_parser.add_argument("query", help="Problem description to search for")
    search_parser.add_argument(
        "--domain-type",
        choices=DOMAIN_TYPES,
        help="Filter by domain type",
    )
    search_parser.add_argument(
        "--domain", "-d",
        help="Full domain context as JSON",
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Maximum number of results (default: 5)",
    )
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Minimum similarity threshold (default: 0.75)",
    )

    # get command
    get_parser = subparsers.add_parser(
        "get", help="Get experience by ID", parents=[parent_parser]
    )
    get_parser.add_argument("experience_id", help="Experience ID")

    # update-success command
    update_parser = subparsers.add_parser(
        "update-success", help="Update success count", parents=[parent_parser]
    )
    update_parser.add_argument("experience_id", help="Experience ID")
    update_parser.add_argument(
        "--increment", "-i",
        type=int,
        default=1,
        help="Amount to increment (default: 1)",
    )

    # feedback command
    feedback_parser = subparsers.add_parser(
        "feedback", help="Record retrieval feedback", parents=[parent_parser]
    )
    feedback_parser.add_argument("experience_id", help="Experience ID")
    feedback_parser.add_argument(
        "--outcome",
        choices=["used", "ignored", "helped", "hurt"],
        required=True,
        help="Retrieval outcome",
    )

    # clear command
    clear_parser = subparsers.add_parser(
        "clear", help="Clear experiences (optionally for specific domain)", parents=[parent_parser]
    )
    clear_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm clearing experiences",
    )
    clear_parser.add_argument(
        "--domain-type",
        choices=DOMAIN_TYPES,
        help="Clear only this domain",
    )

    # categories command
    subparsers.add_parser(
        "categories", help="List all categories", parents=[parent_parser]
    )

    # domains command
    subparsers.add_parser(
        "domains", help="List all domains with experiences", parents=[parent_parser]
    )

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Check dependencies
    if not CHROMADB_AVAILABLE:
        print("Note: ChromaDB not available, using JSON fallback storage", file=sys.stderr)
        print("Install with: pip install chromadb", file=sys.stderr)

    if not EMBEDDINGS_AVAILABLE:
        print("Note: sentence-transformers not available, using hash-based embeddings", file=sys.stderr)
        print("Install with: pip install sentence-transformers", file=sys.stderr)

    # Initialize store
    store = ExperienceStore(
        db_dir=args.db_dir,
        use_embeddings=not args.no_embeddings,
    )

    # Dispatch to command handler
    commands = {
        "store": cmd_store,
        "stats": cmd_stats,
        "list": cmd_list,
        "search": cmd_search,
        "get": cmd_get,
        "update-success": cmd_update_success,
        "feedback": cmd_feedback,
        "clear": cmd_clear,
        "categories": cmd_categories,
        "domains": cmd_domains,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, store)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
