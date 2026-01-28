#!/usr/bin/env python3
"""
semantic-matcher.py - Ultra-Fast Hybrid Agent Discovery

Uses sentence-transformers for semantic similarity combined with keyword matching
for robust agent selection. Optimized for speed with:
- Pre-computed agent embeddings (cached to disk)
- Model singleton (loaded once per process)
- LRU query cache (avoids re-embedding recent queries)
- Tiered early-exit (skips semantic if keyword match is confident)
- Batch matrix operations (vectorized similarity computation)

Usage:
    python semantic-matcher.py select "story text" [agents_dir]
    python semantic-matcher.py embed-agents [agents_dir]
    python semantic-matcher.py similarity "text1" "text2"
    python semantic-matcher.py benchmark [agents_dir]
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from functools import lru_cache

# Configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, good quality, 384 dimensions
CACHE_FILE = ".agent-embeddings.json"
QUERY_CACHE_SIZE = 128  # LRU cache for query embeddings
KEYWORD_WEIGHT = 0.3
SEMANTIC_WEIGHT = 0.7
MAX_AGENTS = 2
MIN_SIMILARITY = 0.3
HIGH_CONFIDENCE_KEYWORD_THRESHOLD = 0.85  # Skip semantic if keyword score > this

# Global model singleton (loaded once per process)
_model_instance = None
_embeddings_cache = {}  # In-memory cache for agent embeddings

# Agent tier definitions
TIER1_AGENTS = {"code-reviewer", "test-runner", "debugger", "security-auditor", "git-workflow"}
TIER2_AGENTS = {"python-dev", "typescript-specialist", "frontend-developer", "backend-architect",
                "api-designer", "ml-engineer", "devops-engineer", "documentation-writer",
                "refactoring-specialist", "performance-optimizer", "data-scientist",
                "prompt-engineer", "dependency-manager", "first-principles-analyst",
                "product-strategist", "contrarian-challenger", "code-explainer"}
TIER3_AGENTS = {"vision-analyst", "sensor-fusion", "safety-supervisor", "compliance-guardian",
                "anomaly-detector", "decision-planner", "device-controller", "alert-dispatcher",
                "warehouse-orchestrator", "quality-inspector", "datacenter-optimizer"}

# Keyword mappings for fast matching
KEYWORD_MAP = {
    # Testing
    "test": "test-runner", "tests": "test-runner", "testing": "test-runner",
    "jest": "test-runner", "pytest": "test-runner", "coverage": "test-runner",
    "unit test": "test-runner", "integration test": "test-runner",

    # Security
    "security": "security-auditor", "vulnerability": "security-auditor",
    "owasp": "security-auditor", "cve": "security-auditor", "audit": "security-auditor",
    "authentication": "security-auditor", "authorization": "security-auditor",
    "injection": "security-auditor", "xss": "security-auditor",

    # Code review
    "review": "code-reviewer", "code review": "code-reviewer", "pr review": "code-reviewer",

    # Debugging
    "debug": "debugger", "bug": "debugger", "error": "debugger",
    "crash": "debugger", "exception": "debugger", "fix bug": "debugger",

    # Git
    "git": "git-workflow", "commit": "git-workflow", "branch": "git-workflow",
    "merge": "git-workflow", "rebase": "git-workflow",

    # Python
    "python": "python-dev", "django": "python-dev", "flask": "python-dev",
    "fastapi": "python-dev", "pip": "python-dev", "poetry": "python-dev",

    # TypeScript
    "typescript": "typescript-specialist", "ts": "typescript-specialist",

    # Frontend
    "react": "frontend-developer", "vue": "frontend-developer", "angular": "frontend-developer",
    "css": "frontend-developer", "frontend": "frontend-developer", "ui": "frontend-developer",

    # Backend
    "architecture": "backend-architect", "microservice": "backend-architect",
    "scalability": "backend-architect", "system design": "backend-architect",

    # API
    "api": "api-designer", "rest": "api-designer", "graphql": "api-designer",
    "endpoint": "api-designer", "openapi": "api-designer",

    # ML
    "ml": "ml-engineer", "machine learning": "ml-engineer", "pytorch": "ml-engineer",
    "tensorflow": "ml-engineer", "model training": "ml-engineer",

    # DevOps
    "docker": "devops-engineer", "kubernetes": "devops-engineer", "k8s": "devops-engineer",
    "ci/cd": "devops-engineer", "deploy": "devops-engineer", "pipeline": "devops-engineer",

    # Documentation
    "document": "documentation-writer", "readme": "documentation-writer",
    "docs": "documentation-writer", "documentation": "documentation-writer",

    # Performance
    "performance": "performance-optimizer", "optimize": "performance-optimizer",
    "slow": "performance-optimizer", "benchmark": "performance-optimizer",

    # Refactoring
    "refactor": "refactoring-specialist", "clean up": "refactoring-specialist",
    "technical debt": "refactoring-specialist",
}


def get_model():
    """
    Get the sentence transformer model (singleton pattern).

    Model is loaded once and cached for the entire process lifetime.
    This avoids the ~500ms model loading overhead on subsequent calls.
    """
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    try:
        from sentence_transformers import SentenceTransformer
        _model_instance = SentenceTransformer(EMBEDDING_MODEL)
        return _model_instance
    except ImportError:
        print("Warning: sentence-transformers not installed. Using keyword-only matching.",
              file=sys.stderr)
        return None


@lru_cache(maxsize=QUERY_CACHE_SIZE)
def _embed_query_cached(text_hash: str, text: str) -> Optional[Tuple]:
    """
    Cache query embeddings using LRU cache.

    The text_hash is used as the cache key to handle the unhashable numpy array.
    Returns tuple (for hashability) or None if model unavailable.
    """
    model = get_model()
    if model is None:
        return None
    embedding = model.encode(text)
    return tuple(embedding.tolist())


def embed_query(text: str) -> Optional[list]:
    """
    Embed a query with caching.

    Uses LRU cache to avoid re-embedding recent queries.
    Returns list or None if model unavailable.
    """
    text_hash = hashlib.md5(text.encode()).hexdigest()
    result = _embed_query_cached(text_hash, text)
    return list(result) if result else None


def extract_agent_info(file_path: Path) -> Dict:
    """Extract agent name, description, and keywords from markdown file."""
    content = file_path.read_text()
    name = file_path.stem

    # Extract description from YAML frontmatter
    description = ""
    if content.startswith("---"):
        try:
            end_idx = content.index("---", 3)
            frontmatter = content[3:end_idx]
            for line in frontmatter.split("\n"):
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')
                    break
        except ValueError:
            pass

    # If no frontmatter description, use first paragraph
    if not description:
        lines = content.split("\n")
        for line in lines:
            if line.strip() and not line.startswith("#") and not line.startswith("---"):
                description = line.strip()[:500]
                break

    # Extract keywords from name and content
    keywords = set(name.replace("-", " ").split())

    # Add common terms from content
    content_lower = content.lower()
    for term in ["python", "typescript", "javascript", "react", "api", "test",
                 "security", "debug", "deploy", "docker", "git"]:
        if term in content_lower:
            keywords.add(term)

    return {
        "name": name,
        "description": description,
        "keywords": list(keywords),
        "file": str(file_path),
        "tier": get_tier(name)
    }


def get_tier(agent_name: str) -> int:
    """Get the tier level for an agent."""
    if agent_name in TIER1_AGENTS:
        return 1
    elif agent_name in TIER2_AGENTS:
        return 2
    elif agent_name in TIER3_AGENTS:
        return 3
    return 4


def compute_embeddings(agents_dir: Path) -> Dict:
    """Compute embeddings for all agents and cache them."""
    model = get_model()
    if model is None:
        return {}

    agents = {}

    # Find all agent markdown files
    for pattern in ["*.md", "*/*.md", "*/*/*.md"]:
        for file_path in agents_dir.glob(pattern):
            if file_path.name in ["README.md", "SKILL.md"]:
                continue
            if file_path.name[0].isupper():
                continue

            info = extract_agent_info(file_path)

            # Create embedding text from name + description + keywords
            embed_text = f"{info['name'].replace('-', ' ')}: {info['description']} {' '.join(info['keywords'])}"

            # Compute embedding
            embedding = model.encode(embed_text).tolist()

            agents[info['name']] = {
                **info,
                "embedding": embedding,
                "embed_text": embed_text
            }

    return agents


def load_or_compute_embeddings(agents_dir: Path) -> Dict:
    """
    Load cached embeddings or compute them.

    Uses a two-tier caching strategy:
    1. In-memory cache (fastest, persists for process lifetime)
    2. Disk cache (.agent-embeddings.json, persists across runs)
    """
    global _embeddings_cache

    # Tier 1: Check in-memory cache first (instant)
    cache_key = str(agents_dir.resolve())
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key]

    # Tier 2: Check disk cache
    cache_path = agents_dir / CACHE_FILE
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
            # Verify cache is still valid (simple check)
            if cache.get("model") == EMBEDDING_MODEL:
                agents = cache.get("agents", {})
                # Store in memory for next time
                _embeddings_cache[cache_key] = agents
                return agents
        except json.JSONDecodeError:
            pass

    # Tier 3: Compute fresh embeddings (slow, but only happens once)
    agents = compute_embeddings(agents_dir)

    # Save to both caches
    if agents:
        # Memory cache
        _embeddings_cache[cache_key] = agents
        # Disk cache
        cache = {
            "model": EMBEDDING_MODEL,
            "agents": agents
        }
        cache_path.write_text(json.dumps(cache, indent=2))

    return agents


def keyword_match(text: str, enabled_tiers: set) -> Dict[str, float]:
    """Fast keyword-based matching. Returns agent -> score mapping."""
    text_lower = text.lower()
    scores = {}

    for keyword, agent in KEYWORD_MAP.items():
        if keyword in text_lower:
            tier = get_tier(agent)
            if tier in enabled_tiers:
                # Higher score for longer keyword matches
                score = len(keyword.split()) * 0.5
                scores[agent] = max(scores.get(agent, 0), score)

    # Normalize scores to 0-1 range
    if scores:
        max_score = max(scores.values())
        scores = {k: v / max_score for k, v in scores.items()}

    return scores


def semantic_match(text: str, agents: Dict, enabled_tiers: set) -> Dict[str, float]:
    """
    Embedding-based semantic matching with batch computation.

    Uses vectorized operations for fast similarity computation across all agents.
    Returns agent -> similarity mapping.
    """
    if not agents:
        return {}

    # Get query embedding (uses LRU cache)
    query_embedding = embed_query(text)
    if query_embedding is None:
        return {}

    import numpy as np
    query_vec = np.array(query_embedding)
    query_norm = np.linalg.norm(query_vec)

    # Filter agents by tier and collect embeddings for batch processing
    eligible_agents = []
    embeddings = []
    for name, info in agents.items():
        tier = info.get("tier", 4)
        if tier not in enabled_tiers:
            continue
        if "embedding" not in info:
            continue
        eligible_agents.append(name)
        embeddings.append(info["embedding"])

    if not eligible_agents:
        return {}

    # Batch cosine similarity using matrix multiplication
    # This is much faster than per-agent loops for >10 agents
    embedding_matrix = np.array(embeddings)  # Shape: (n_agents, embedding_dim)
    norms = np.linalg.norm(embedding_matrix, axis=1)  # Shape: (n_agents,)

    # Dot product: query · each_agent
    dots = np.dot(embedding_matrix, query_vec)  # Shape: (n_agents,)

    # Cosine similarity = dot / (norm1 * norm2)
    similarities = dots / (norms * query_norm)

    # Build result dict, filtering by minimum similarity
    scores = {}
    for i, name in enumerate(eligible_agents):
        if similarities[i] >= MIN_SIMILARITY:
            scores[name] = float(similarities[i])

    return scores


def hybrid_select(text: str, agents_dir: Optional[Path] = None,
                  enabled_tiers: str = "1,2", max_agents: int = MAX_AGENTS) -> List[str]:
    """
    Ultra-fast hybrid agent selection combining keyword and semantic matching.

    Optimization strategy:
    1. FAST PATH: Keyword matching first (~0.1ms)
    2. EARLY EXIT: If keyword match is high-confidence, skip semantic
    3. SLOW PATH: Semantic matching only when needed (~50ms first time, <1ms cached)

    Returns list of selected agent names, ordered by relevance.
    """
    enabled_tiers_set = set(int(t) for t in enabled_tiers.split(","))

    # STEP 1: Fast keyword matching (~0.1ms)
    keyword_scores = keyword_match(text, enabled_tiers_set)

    # STEP 2: Early exit if keyword match is high-confidence
    # This avoids the slower semantic matching for common cases
    if keyword_scores:
        top_score = max(keyword_scores.values())
        if top_score >= HIGH_CONFIDENCE_KEYWORD_THRESHOLD:
            # High confidence keyword match - skip semantic for speed
            sorted_agents = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
            return [agent for agent, _ in sorted_agents[:max_agents]]

    # STEP 3: Semantic matching (slower, but more accurate for ambiguous queries)
    semantic_scores = {}

    # Check bundled agents first (always available)
    script_dir = Path(__file__).parent.parent
    bundled_dir = script_dir / "agents"
    if bundled_dir.exists():
        bundled_agents = load_or_compute_embeddings(bundled_dir)
        semantic_scores = semantic_match(text, bundled_agents, enabled_tiers_set)

    # Also check external agents if provided
    if agents_dir and agents_dir.exists():
        external_agents = load_or_compute_embeddings(agents_dir)
        external_semantic = semantic_match(text, external_agents, enabled_tiers_set)
        # Merge (external can override bundled for same agent)
        for name, score in external_semantic.items():
            if name not in semantic_scores or score > semantic_scores[name]:
                semantic_scores[name] = score

    # STEP 4: Combine scores using weighted average
    all_agents = set(keyword_scores.keys()) | set(semantic_scores.keys())
    combined_scores = {}

    for agent in all_agents:
        kw_score = keyword_scores.get(agent, 0)
        sem_score = semantic_scores.get(agent, 0)

        # Scoring strategy:
        # - Both methods agree: full weight combination
        # - Semantic-only: slight penalty (may be false positive)
        # - Keyword-only: larger penalty (less contextual)
        if kw_score == 0:
            combined = sem_score * 0.8  # Slight penalty for semantic-only
        elif sem_score == 0:
            combined = kw_score * 0.6   # Larger penalty for keyword-only
        else:
            # Both methods found it - use weighted combination
            combined = KEYWORD_WEIGHT * kw_score + SEMANTIC_WEIGHT * sem_score

        combined_scores[agent] = combined

    # Sort by score and return top N
    sorted_agents = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    return [agent for agent, _ in sorted_agents[:max_agents]]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "select":
        if len(sys.argv) < 3:
            print("Usage: semantic-matcher.py select <story-text> [agents-dir] [tiers] [max-agents]")
            sys.exit(1)

        text = sys.argv[2]
        agents_dir = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
        tiers = sys.argv[4] if len(sys.argv) > 4 else "1,2"
        max_agents = int(sys.argv[5]) if len(sys.argv) > 5 else MAX_AGENTS

        selected = hybrid_select(text, agents_dir, tiers, max_agents)
        for agent in selected:
            print(agent)

    elif command == "embed-agents":
        agents_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "agents"

        if not agents_dir.exists():
            print(f"Error: Directory not found: {agents_dir}", file=sys.stderr)
            sys.exit(1)

        agents = compute_embeddings(agents_dir)

        # Save cache
        cache_path = agents_dir / CACHE_FILE
        cache = {"model": EMBEDDING_MODEL, "agents": agents}
        cache_path.write_text(json.dumps(cache, indent=2))

        print(f"Computed embeddings for {len(agents)} agents")
        print(f"Cache saved to: {cache_path}")

    elif command == "similarity":
        if len(sys.argv) < 4:
            print("Usage: semantic-matcher.py similarity <text1> <text2>")
            sys.exit(1)

        model = get_model()
        if model is None:
            print("Error: sentence-transformers not available")
            sys.exit(1)

        import numpy as np
        emb1 = model.encode(sys.argv[2])
        emb2 = model.encode(sys.argv[3])
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        print(f"Similarity: {similarity:.4f}")

    elif command == "list":
        agents_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "agents"
        agents = load_or_compute_embeddings(agents_dir)

        for name, info in sorted(agents.items()):
            has_embedding = "embedding" in info
            print(f"  {name} (tier {info.get('tier', '?')}) {'[embedded]' if has_embedding else ''}")

    elif command == "benchmark":
        import time

        agents_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

        # Test queries
        test_queries = [
            "Add unit tests for the authentication module",
            "Fix the bug in the user registration flow",
            "Optimize database query performance",
            "Implement API endpoint for user profiles",
            "Review code for security vulnerabilities",
            "Deploy the application to production",
            "Refactor the legacy payment module",
            "Add TypeScript types to the frontend",
        ]

        print("=" * 60)
        print("Agent Discovery Benchmark")
        print("=" * 60)
        print()

        # Cold start (first query includes model loading)
        print("Cold start (includes model loading):")
        start = time.perf_counter()
        hybrid_select(test_queries[0], agents_dir)
        cold_time = (time.perf_counter() - start) * 1000
        print(f"  First query: {cold_time:.1f}ms")
        print()

        # Warm queries (model already loaded, cache populated)
        print("Warm queries (model cached):")
        times = []
        for query in test_queries[1:]:
            start = time.perf_counter()
            result = hybrid_select(query, agents_dir)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            print(f"  '{query[:40]}...' -> {result} ({elapsed:.2f}ms)")

        print()
        print(f"Average warm query: {sum(times)/len(times):.2f}ms")
        print(f"Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")
        print()

        # Cached query (exact same query)
        print("Cached query (exact same text):")
        start = time.perf_counter()
        hybrid_select(test_queries[1], agents_dir)
        cached_time = (time.perf_counter() - start) * 1000
        print(f"  Cached: {cached_time:.2f}ms")
        print()

        # Summary
        print("=" * 60)
        print("Summary:")
        print(f"  Cold start:     {cold_time:.1f}ms (includes model loading)")
        print(f"  Warm query:     {sum(times)/len(times):.2f}ms (model cached)")
        print(f"  Cached query:   {cached_time:.2f}ms (query embedding cached)")
        print("=" * 60)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
