# Documentation Style Guide

This guide defines documentation standards for the claude-loop codebase to ensure consistency, clarity, and maintainability.

## Table of Contents

1. [Python Docstring Format](#python-docstring-format)
2. [Shell Function Documentation](#shell-function-documentation)
3. [Inline Comments](#inline-comments)
4. [Complex Logic Documentation](#complex-logic-documentation)
5. [Configuration Documentation](#configuration-documentation)
6. [Examples](#examples)

---

## Python Docstring Format

Use **Google style docstrings** for all Python functions, classes, and modules.

### Module Docstrings

```python
"""Brief one-line summary of the module.

More detailed description of the module's purpose, key classes,
and typical usage patterns. Can span multiple paragraphs.

Example:
    from lib import experience_store

    store = experience_store.ExperienceStore()
    results = store.retrieve("user query", limit=10)

Attributes:
    MODULE_CONSTANT (str): Description of module-level constant.
"""
```

### Function Docstrings

```python
def retrieve_experiences(query: str, limit: int = 10, min_score: float = 0.7) -> list[dict]:
    """Retrieve relevant experiences from the vector store.

    Searches the ChromaDB vector store for experiences semantically similar
    to the query. Applies recency decay and helpful_rate boosting to ranking.

    Args:
        query: The search query string (typically a user story description).
        limit: Maximum number of experiences to return. Defaults to 10.
        min_score: Minimum similarity score threshold (0.0-1.0). Experiences
            below this threshold are filtered out. Defaults to 0.7.

    Returns:
        A list of experience dictionaries, each containing:
            - id (str): Unique experience identifier
            - content (str): The experience text
            - score (float): Similarity score (0.0-1.0)
            - last_used (str): ISO timestamp of last usage
            - helpful_rate (float): Positive feedback ratio (0.0-1.0)

    Raises:
        ConnectionError: If ChromaDB connection fails.
        ValueError: If limit < 1 or min_score not in [0.0, 1.0].

    Example:
        >>> store = ExperienceStore()
        >>> results = store.retrieve_experiences(
        ...     "implement user authentication",
        ...     limit=5,
        ...     min_score=0.8
        ... )
        >>> print(f"Found {len(results)} relevant experiences")
        Found 3 relevant experiences

    Note:
        Results are ordered by combined score (similarity * recency * helpful_rate).
        Recency decay uses exponential half-life of 30 days.
    """
```

### Class Docstrings

```python
class ExperienceStore:
    """Vector store for persisting and retrieving past execution experiences.

    Uses ChromaDB for vector similarity search with custom ranking that combines
    semantic similarity, recency, and helpfulness ratings. Stores experiences
    with metadata for filtering and analysis.

    Attributes:
        client: ChromaDB PersistentClient instance.
        collection: ChromaDB collection for experiences.
        embedding_function: Function to generate embeddings from text.

    Example:
        >>> store = ExperienceStore()
        >>> store.add_experience(
        ...     content="Fixed auth bug by checking token expiry",
        ...     metadata={"story_id": "US-001", "success": True}
        ... )
        >>> results = store.retrieve("authentication issues")
    """
```

---

## Shell Function Documentation

All shell functions must have a header comment block following this format:

```bash
###############################################################################
# Brief one-line summary of the function
#
# Detailed description of what the function does, any important behavior,
# and edge cases to be aware of.
#
# Arguments:
#   $1 - Description of first positional argument (type, constraints)
#   $2 - Description of second argument (optional if applicable)
#   ... - Variable arguments (if applicable)
#
# Environment Variables:
#   VAR_NAME - Description of environment variable used (if any)
#
# Returns:
#   Description of return value or side effects
#   Exit code: 0 on success, non-zero on failure
#
# Outputs:
#   stdout: What is printed to stdout (if anything)
#   stderr: What is printed to stderr (if anything)
#
# Example:
#   validate_prd "prd.json"
#   if [ $? -eq 0 ]; then
#     echo "PRD is valid"
#   fi
#
# Notes:
#   - Any important caveats or warnings
#   - Performance considerations
#   - Thread safety information
###############################################################################
function_name() {
  local arg1=$1
  local arg2=${2:-default_value}

  # Implementation
}
```

### Minimal Documentation (for simple functions)

```bash
###############################################################################
# Check if a story exists in the PRD
# Args: $1 = story ID
# Returns: 0 if exists, 1 if not found
###############################################################################
story_exists() {
  local story_id=$1
  jq -e --arg id "$story_id" '.userStories[] | select(.id == $id)' "$PRD_FILE" >/dev/null 2>&1
}
```

---

## Inline Comments

### When to Add Inline Comments

**DO comment:**
- Complex algorithms or non-obvious logic
- Workarounds for bugs or limitations
- Security-critical sections
- Performance optimizations
- Edge cases and their handling
- Regex patterns and jq queries
- TODO/FIXME/HACK markers

**DON'T comment:**
- Obvious code (`i++  # increment i`)
- Code that can be made self-documenting with better naming
- Redundant information already in function docstring

### Comment Style

```python
# Single-line comment explaining the next line
result = complex_function()

# Multi-line comment explaining a block of code
# Line 2 of the explanation
# Line 3 of the explanation
for item in items:
    process(item)

# Regex pattern: Matches story IDs in format "US-###" or "IMP-###"
# Examples: "US-001", "IMP-042"
# Allows leading zeros and requires exactly 3 digits
story_id_pattern = r'^(US|IMP)-\d{3}$'

# Complex jq query: Extract stories with dependencies satisfied
# 1. Filter to stories where "passes" is false
# 2. For each story, check if all dependencies have "passes" = true
# 3. Select stories where ALL dependencies are satisfied
ready_stories=$(jq -r '
  .userStories[] |
  select(.passes == false) |
  select(
    (.dependencies // []) as $deps |
    $deps | length == 0 or
    all($deps[]; . as $dep | any(.userStories[]; .id == $dep and .passes == true))
  ) |
  .id
' "$prd_file")
```

### Documenting Error Handling

```python
try:
    result = api_call()
except requests.Timeout:
    # Network timeout after 30s. Retry with exponential backoff.
    # If all retries fail, return cached result or None.
    result = retry_with_backoff(api_call)
except requests.HTTPError as e:
    # HTTP error (4xx/5xx). Check if it's a rate limit (429)
    # or authentication issue (401/403) for better error messages.
    if e.response.status_code == 429:
        logger.warning("Rate limited, backing off...")
        time.sleep(60)
    raise
```

### Documenting Edge Cases

```bash
# Edge case: Empty story list returns immediately
if [ ${#stories[@]} -eq 0 ]; then
  echo "[]"
  return 0
fi

# Edge case: Single story with no dependencies always ready
if [ ${#stories[@]} -eq 1 ] && [ -z "$dependencies" ]; then
  echo "${stories[0]}"
  return 0
fi

# Edge case: Circular dependencies detected - fail fast
if check_circular_dependencies "$prd_file"; then
  error "Circular dependencies detected in PRD"
  return 1
fi
```

---

## Complex Logic Documentation

For algorithms, data structures, or complex workflows, provide high-level overview before implementation:

```python
def topological_sort(self) -> list[str]:
    """Topological sort of stories by dependencies using Kahn's algorithm.

    Algorithm Overview:
    1. Calculate in-degree for each story (number of dependencies)
    2. Initialize queue with stories that have in-degree = 0 (no dependencies)
    3. Process queue in priority order (lower priority number = higher priority)
    4. For each processed story, decrement in-degree of dependent stories
    5. Add newly zero-in-degree stories to queue
    6. Repeat until queue is empty
    7. If not all stories processed, circular dependency exists

    Time Complexity: O(V + E) where V = stories, E = dependency edges
    Space Complexity: O(V) for in-degree map and queue

    Example:
        Stories: A(prio=1) -> B(prio=2) -> C(prio=3)
                 A -> D(prio=1)

        Result: [A, D, B, C]  # A first (no deps), then D (same priority as A),
                               # then B (depends on A), then C (depends on B)
    """
    # Implementation following algorithm described above
    in_degree = {}
    # ... rest of implementation
```

```bash
###############################################################################
# Parallel execution coordinator using worker pools
#
# Algorithm:
#   1. Get dependency batches from dependency-graph.py (stories with no blocking deps)
#   2. For each batch:
#      a. Check for file conflicts between stories
#      b. If conflicts exist, split batch into conflict-free groups
#      c. Launch up to max_workers concurrent worker processes
#      d. Wait for workers to complete (blocking)
#      e. Collect results and check for failures
#      f. Update PRD with completion status
#   3. If any batch has failures, halt execution and report
#   4. Continue to next batch if current batch succeeds
#
# Data Flow:
#   PRD -> dependency-graph.py -> batches JSON -> launch workers -> collect results -> update PRD
#
# File Structure:
#   .claude-loop/
#     workers/
#       US-001_20260114_120000/   # Worker directory per story
#         logs/
#           output.log              # Worker stdout
#           error.log               # Worker stderr
#           combined.log            # Combined output
#         result.json               # Worker result with success/failure
#     tracking/
#       parallel_workers.txt        # Active worker tracking file
#
# Concurrency Safety:
#   - File-based worker tracking (bash 3.x compatible)
#   - Workers isolated in separate directories
#   - No shared state between workers
#   - PRD updates serialized after batch completion
###############################################################################
execute_parallel_batches() {
  # Implementation
}
```

---

## Configuration Documentation

### Environment Variables

Document all environment variables in a centralized reference file:

**File:** `docs/ENVIRONMENT-VARIABLES.md`

```markdown
# Environment Variables Reference

## Required Variables

### ANTHROPIC_API_KEY
- **Type:** String (API key)
- **Required:** Yes
- **Description:** Anthropic API key for Claude API access
- **Example:** `sk-ant-...`
- **Used by:** All Claude API calls throughout the system
- **Security:** Never commit this to version control. Store in `.env` or system environment.

## Optional Variables

### CLAUDE_LOOP_LOG_LEVEL
- **Type:** String (DEBUG|INFO|WARN|ERROR)
- **Required:** No
- **Default:** `INFO`
- **Description:** Controls logging verbosity
- **Example:** `CLAUDE_LOOP_LOG_LEVEL=DEBUG ./claude-loop.sh prd.json`
- **Used by:** `lib/structured-logging.sh`, all modules that log

### CLAUDE_LOOP_MAX_ITERATIONS
- **Type:** Integer
- **Required:** No
- **Default:** `100`
- **Description:** Maximum number of iterations before auto-stopping
- **Example:** `CLAUDE_LOOP_MAX_ITERATIONS=50 ./claude-loop.sh prd.json`
- **Used by:** `claude-loop.sh` main loop

### CLAUDE_LOOP_PARALLEL_MAX_WORKERS
- **Type:** Integer (1-10)
- **Required:** No
- **Default:** `3`
- **Description:** Maximum concurrent workers for parallel execution
- **Example:** `CLAUDE_LOOP_PARALLEL_MAX_WORKERS=5 ./claude-loop.sh --parallel prd.json`
- **Used by:** `lib/parallel.sh`
- **Note:** Higher values increase CPU/memory usage. Recommended: 2-4 for most systems.
```

### Configuration File Format

Document configuration files with inline comments:

```json
{
  "_comment": "Claude Loop Configuration",
  "_docs": "https://github.com/user/claude-loop/blob/main/docs/configuration.md",

  "project": "my-project",
  "branchName": "feature/my-feature",

  "parallelization": {
    "_comment": "Parallel execution settings",
    "enabled": true,
    "maxWorkers": 3,
    "_docs_maxWorkers": "Higher values (4-8) for powerful machines, lower (2-3) for laptops",

    "defaultModel": "sonnet",
    "_docs_defaultModel": "Options: haiku (fast/cheap), sonnet (balanced), opus (best quality)",

    "modelStrategy": "auto",
    "_docs_modelStrategy": "Options: auto (smart selection), always-opus, always-sonnet, always-haiku"
  }
}
```

---

## Examples

### Well-Documented Python Module

```python
"""Experience retrieval with semantic search and ranking.

This module provides the ExperienceRetriever class for fetching relevant
past experiences from the vector store. It combines semantic similarity
with recency decay and helpfulness ratings to rank results.

Typical usage:
    retriever = ExperienceRetriever()
    experiences = retriever.retrieve(
        "implement user authentication",
        limit=5,
        min_score=0.7
    )

Attributes:
    RECENCY_HALF_LIFE_DAYS (int): Days for recency score to decay by 50%.
    MIN_HELPFUL_RATE (float): Minimum helpful rate for experience inclusion.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from chromadb import PersistentClient
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

# Recency decay: score halves every 30 days
RECENCY_HALF_LIFE_DAYS = 30

# Filter out experiences with <30% helpful rate
MIN_HELPFUL_RATE = 0.3


class ExperienceRetriever:
    """Retrieves and ranks past experiences from vector store.

    Combines semantic search with custom ranking based on:
    1. Semantic similarity (ChromaDB cosine similarity)
    2. Recency decay (exponential, half-life = 30 days)
    3. Helpfulness (user feedback ratio)

    Attributes:
        client: ChromaDB PersistentClient for storage.
        collection: ChromaDB collection containing experiences.
        embedding_fn: Sentence-transformers embedding function.
    """

    def __init__(self, db_path: str = ".claude-loop/chroma"):
        """Initialize the experience retriever.

        Args:
            db_path: Path to ChromaDB persistent storage directory.
                Defaults to ".claude-loop/chroma".

        Raises:
            ConnectionError: If ChromaDB initialization fails.
        """
        try:
            self.client = PersistentClient(path=db_path)
            # Use sentence-transformers for embeddings
            # Model: all-MiniLM-L6-v2 (384 dimensions, fast inference)
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.collection = self.client.get_or_create_collection(
                name="experiences",
                embedding_function=self.embedding_fn
            )
            logger.info(f"Initialized ExperienceRetriever with db_path={db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise ConnectionError(f"ChromaDB initialization failed: {e}") from e

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.7
    ) -> list[dict]:
        """Retrieve relevant experiences matching the query.

        Searches vector store for semantically similar experiences and ranks
        them by combined score (similarity * recency * helpfulness).

        Args:
            query: Search query (typically user story description).
            limit: Maximum number of results. Must be > 0.
            min_score: Minimum similarity threshold (0.0-1.0). Experiences
                below this are filtered out.

        Returns:
            List of experience dicts sorted by ranking score (descending).
            Each dict contains: id, content, score, metadata, ranking_score.

        Raises:
            ValueError: If limit < 1 or min_score not in [0.0, 1.0].
            ConnectionError: If ChromaDB query fails.

        Example:
            >>> retriever = ExperienceRetriever()
            >>> results = retriever.retrieve("authentication bug", limit=3)
            >>> for exp in results:
            ...     print(f"{exp['id']}: {exp['ranking_score']:.2f}")
            exp-123: 0.92
            exp-456: 0.85
            exp-789: 0.78
        """
        # Validate inputs
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError(f"min_score must be in [0.0, 1.0], got {min_score}")

        try:
            # Query ChromaDB for top candidates (fetch 2x limit for filtering)
            results = self.collection.query(
                query_texts=[query],
                n_results=limit * 2,
                include=["documents", "metadatas", "distances"]
            )

            # No results found
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                logger.info(f"No experiences found for query: {query}")
                return []

            # Process and rank results
            ranked = self._rank_experiences(
                ids=results['ids'][0],
                documents=results['documents'][0],
                distances=results['distances'][0],
                metadatas=results['metadatas'][0],
                min_score=min_score
            )

            # Return top N after ranking and filtering
            return ranked[:limit]

        except Exception as e:
            logger.error(f"Experience retrieval failed: {e}")
            raise ConnectionError(f"ChromaDB query failed: {e}") from e

    def _rank_experiences(
        self,
        ids: list[str],
        documents: list[str],
        distances: list[float],
        metadatas: list[dict],
        min_score: float
    ) -> list[dict]:
        """Rank experiences by combined score.

        Combines three factors:
        1. Similarity: 1 - (distance / 2)  # ChromaDB uses L2 distance
        2. Recency: 0.5 ^ (days_ago / HALF_LIFE)
        3. Helpfulness: helpful_rate from metadata

        Final score = similarity * recency * (0.5 + 0.5 * helpful_rate)

        Args:
            ids: Experience IDs from ChromaDB.
            documents: Experience text content.
            distances: L2 distances (0 = perfect match, 2 = opposite).
            metadatas: Metadata dicts with last_used, helpful_rate fields.
            min_score: Minimum similarity threshold for filtering.

        Returns:
            Sorted list of experience dicts (highest score first).

        Note:
            Helpfulness is weighted 50% (ranges from 0.5 to 1.0 in final score)
            so that even unhelpful experiences can be retrieved if very relevant.
        """
        now = datetime.now(timezone.utc)
        ranked = []

        for i, exp_id in enumerate(ids):
            # Convert ChromaDB L2 distance to similarity (0-1 scale)
            # Distance: 0 (identical) to 2 (opposite)
            similarity = max(0.0, 1.0 - (distances[i] / 2.0))

            # Skip if below threshold
            if similarity < min_score:
                continue

            metadata = metadatas[i] or {}

            # Calculate recency factor with exponential decay
            last_used_str = metadata.get('last_used', now.isoformat())
            last_used = datetime.fromisoformat(last_used_str.replace('Z', '+00:00'))
            days_ago = (now - last_used).days
            recency = 0.5 ** (days_ago / RECENCY_HALF_LIFE_DAYS)

            # Get helpful rate (default to 0.5 if not set)
            helpful_rate = float(metadata.get('helpful_rate', 0.5))

            # Filter out consistently unhelpful experiences
            if helpful_rate < MIN_HELPFUL_RATE:
                logger.debug(f"Filtered out {exp_id}: helpful_rate={helpful_rate:.2f}")
                continue

            # Combined ranking score
            # Helpfulness ranges from 0.5-1.0 (so it's a boost, not a filter)
            ranking_score = similarity * recency * (0.5 + 0.5 * helpful_rate)

            ranked.append({
                'id': exp_id,
                'content': documents[i],
                'similarity': similarity,
                'recency': recency,
                'helpful_rate': helpful_rate,
                'ranking_score': ranking_score,
                'metadata': metadata
            })

        # Sort by ranking score (descending)
        ranked.sort(key=lambda x: x['ranking_score'], reverse=True)

        logger.info(f"Ranked {len(ranked)} experiences for retrieval")
        return ranked
```

### Well-Documented Shell Script

```bash
#!/bin/bash
###############################################################################
# PRD Parser and Validator
#
# Validates PRD JSON structure, checks dependencies, and provides query
# functions for accessing PRD data. Ensures PRD schema v2 compliance.
#
# Functions:
#   validate_prd         - Validate PRD structure and required fields
#   get_story_data       - Get full story object by ID
#   get_ready_stories    - Get stories with satisfied dependencies
#   check_circular_deps  - Detect circular dependency chains
#
# Schema:
#   - project (string, required)
#   - branchName (string, required)
#   - userStories (array, required)
#     - id (string, required, format: /^[A-Z]+-\d{3}$/)
#     - title (string, required)
#     - priority (number, required, 1-999)
#     - passes (boolean, required)
#     - dependencies (array[string], optional)
#
# Exit Codes:
#   0 - Validation passed
#   1 - Validation failed (invalid schema, circular deps, etc.)
#   2 - File not found or not readable
#
# Usage:
#   source lib/prd-parser.sh
#   validate_prd "prd.json" || exit 1
#   ready_stories=$(get_ready_stories "prd.json")
#
# Dependencies:
#   - jq (JSON processor)
#   - python3 (for circular dependency detection)
#
# Environment Variables:
#   CLAUDE_LOOP_STRICT_VALIDATION - If "true", enable strict mode (fail on warnings)
###############################################################################

set -euo pipefail

###############################################################################
# Validate PRD file structure and content
#
# Checks:
#   1. File exists and is readable
#   2. Valid JSON format
#   3. Required top-level fields present
#   4. Each story has required fields
#   5. Story IDs are unique
#   6. Dependencies reference valid story IDs
#   7. No circular dependencies
#
# Args:
#   $1 - Path to PRD JSON file
#
# Returns:
#   0 if valid, 1 if invalid
#
# Outputs:
#   stderr: Detailed validation errors with line/field information
#
# Example:
#   if validate_prd "prd.json"; then
#     echo "PRD is valid"
#   else
#     echo "PRD validation failed"
#     exit 1
#   fi
###############################################################################
validate_prd() {
  local prd_file=$1
  local errors=()

  # Check 1: File exists and readable
  if [ ! -f "$prd_file" ] || [ ! -r "$prd_file" ]; then
    echo "❌ PRD file not found or not readable: $prd_file" >&2
    return 2
  fi

  # Check 2: Valid JSON
  if ! jq empty "$prd_file" 2>/dev/null; then
    echo "❌ Invalid JSON format in: $prd_file" >&2
    return 1
  fi

  # Check 3: Required top-level fields
  local required_fields=("project" "branchName" "userStories")
  for field in "${required_fields[@]}"; do
    if ! jq -e ".$field" "$prd_file" >/dev/null 2>&1; then
      errors+=("Missing required field: $field")
    fi
  done

  # Check 4: Story structure validation
  # Iterate through stories and validate each one
  local story_count=$(jq '.userStories | length' "$prd_file")
  for ((i=0; i<story_count; i++)); do
    # Validate single story at index with all required fields
    # Using --argjson to pass index safely
    if ! jq -e --argjson i "$i" '
      .userStories[$i]
      | select(.id and .title and .priority and (.passes != null))
    ' "$prd_file" >/dev/null 2>&1; then
      local story_id=$(jq -r --argjson i "$i" '.userStories[$i].id // "unknown"' "$prd_file")
      errors+=("Story at index $i (ID: $story_id) missing required fields")
    fi
  done

  # Check 5: Story ID uniqueness
  # Extract all story IDs and count duplicates
  local duplicate_ids=$(jq -r '.userStories[].id' "$prd_file" | sort | uniq -d)
  if [ -n "$duplicate_ids" ]; then
    while read -r dup_id; do
      errors+=("Duplicate story ID found: $dup_id")
    done <<< "$duplicate_ids"
  fi

  # Check 6: Dependencies reference valid IDs
  local all_ids=$(jq -r '.userStories[].id' "$prd_file" | tr '\n' ' ')
  for ((i=0; i<story_count; i++)); do
    local story_id=$(jq -r --argjson i "$i" '.userStories[$i].id' "$prd_file")
    local deps=$(jq -r --argjson i "$i" '.userStories[$i].dependencies[]? // empty' "$prd_file")

    # Check each dependency exists
    while read -r dep_id; do
      if [ -n "$dep_id" ] && [[ ! " $all_ids " =~ " $dep_id " ]]; then
        errors+=("Story $story_id has invalid dependency: $dep_id")
      fi
    done <<< "$deps"
  done

  # Check 7: Circular dependencies
  if ! check_circular_dependencies "$prd_file"; then
    errors+=("Circular dependencies detected")
  fi

  # Report errors
  if [ ${#errors[@]} -gt 0 ]; then
    echo "❌ PRD validation failed with ${#errors[@]} error(s):" >&2
    printf '  - %s\n' "${errors[@]}" >&2
    return 1
  fi

  echo "✓ PRD validation passed" >&2
  return 0
}

# Rest of functions with similar documentation...
```

---

## Quick Reference

**Python:**
- Use Google-style docstrings
- Include Args, Returns, Raises, Example sections
- Document complex algorithms with overview first

**Shell:**
- Use structured comment blocks
- List all arguments and return values
- Include examples for non-trivial functions

**Inline:**
- Comment complex logic and edge cases
- Explain non-obvious workarounds
- Document regex patterns and jq queries

**Configuration:**
- Centralize environment variable docs
- Add inline comments to JSON configs
- Link to detailed documentation

For more examples, see existing well-documented modules:
- `lib/experience-retriever.py` (Python reference)
- `lib/prd-parser.sh` (Shell reference)
