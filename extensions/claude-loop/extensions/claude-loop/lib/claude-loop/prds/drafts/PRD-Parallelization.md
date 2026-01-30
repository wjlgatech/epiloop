# PRD: claude-loop v2 - Parallel Execution & Cost Optimization

**Version:** 1.0
**Author:** Wu & Claude
**Date:** January 2025
**Status:** Draft

---

## 1. Problem Statement

claude-loop currently executes user stories **sequentially**, which creates significant inefficiencies:

| Metric | Current State | Problem |
|--------|---------------|---------|
| Execution | Serial (one story at a time) | 3 independent stories take 3x time |
| Model Selection | All Opus ($15/$75 per M tokens) | 10-30x more expensive than needed |
| Context | Full reload every iteration | Redundant token usage |
| State | No caching | Re-reads unchanged files |

**Real Example (prd-p2.json run):**
- US-006, US-007 are independent (no dependencies)
- Both took ~6 minutes each = 12 minutes total
- Could have run in parallel = 6 minutes (2x faster)

**The core problem:** Linear scaling of time and cost when tasks could be parallelized and optimized.

---

## 2. Goals & Non-Goals

### Goals
1. **2-5x faster** execution through parallel story processing
2. **5-10x cheaper** through intelligent model selection
3. **30-50% token reduction** through caching and compression
4. **Maintain reliability** - parallelization must not break git operations

### Non-Goals
- Changing the core iteration logic (prompt.md)
- Supporting non-Claude LLMs (future consideration)
- Distributed execution across machines (v3 scope)

---

## 3. Solution Overview

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATOR LAYER                              │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Parallel Execution Engine                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │ Dependency  │  │   Model     │  │   Context   │               │  │
│  │  │   Graph     │  │  Selector   │  │   Manager   │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
    ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
    │  Worker 1   │       │  Worker 2   │       │  Worker 3   │
    │  (claude)   │       │  (claude)   │       │  (claude)   │
    │  US-006     │       │  US-007     │       │  US-XXX     │
    │  [sonnet]   │       │  [haiku]    │       │  [opus]     │
    └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
           │                     │                     │
           └─────────────────────┼─────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Merge Controller    │
                    │  - Conflict resolution  │
                    │  - Git coordination     │
                    │  - State sync           │
                    └─────────────────────────┘
```

### 3.2 Key Components

| Component | Responsibility |
|-----------|----------------|
| **Dependency Graph** | Analyze story dependencies, identify parallel groups |
| **Model Selector** | Choose optimal model (Haiku/Sonnet/Opus) per story |
| **Context Manager** | Cache files, compress prompts, manage shared state |
| **Workers** | Execute stories in parallel Claude processes |
| **Merge Controller** | Resolve conflicts, coordinate git operations |

---

## 4. Detailed Design

### 4.1 Dependency Graph

#### PRD Schema Extension

```json
{
  "parallelization": {
    "enabled": true,
    "maxWorkers": 3,
    "conflictStrategy": "rebase"
  },
  "userStories": [
    {
      "id": "US-006",
      "title": "Implement browser automation",
      "dependencies": [],
      "estimatedComplexity": "medium",
      "suggestedModel": "sonnet",
      "fileScope": ["agents/computer_use/browser.py"]
    },
    {
      "id": "US-007",
      "title": "Implement macOS automation",
      "dependencies": [],
      "estimatedComplexity": "medium",
      "suggestedModel": "sonnet",
      "fileScope": ["agents/computer_use/macos.py"]
    },
    {
      "id": "US-008",
      "title": "Create orchestrator",
      "dependencies": ["US-006", "US-007"],
      "estimatedComplexity": "high",
      "suggestedModel": "opus",
      "fileScope": ["agents/computer_use/orchestrator.py"]
    }
  ]
}
```

#### Dependency Analysis Algorithm

```python
def build_execution_plan(stories: list[Story]) -> list[ParallelGroup]:
    """
    Build execution plan with parallel groups.

    Returns list of groups that must execute sequentially,
    but stories within each group can run in parallel.
    """
    # Build dependency graph
    graph = {}
    for story in stories:
        graph[story.id] = set(story.dependencies)

    # Topological sort into parallel groups
    groups = []
    remaining = set(graph.keys())
    completed = set()

    while remaining:
        # Find all stories with satisfied dependencies
        ready = {
            s for s in remaining
            if graph[s].issubset(completed)
        }

        if not ready:
            raise CyclicDependencyError()

        groups.append(ParallelGroup(stories=list(ready)))
        completed.update(ready)
        remaining -= ready

    return groups
```

#### Example Execution Plan

```
Input Stories: US-006, US-007, US-008 (US-008 depends on US-006, US-007)

Execution Plan:
  Group 1 (parallel): [US-006, US-007]  ← Run simultaneously
  Group 2 (sequential): [US-008]        ← Wait for Group 1

Time Savings:
  Sequential: 6min + 6min + 6min = 18 min
  Parallel:   max(6min, 6min) + 6min = 12 min  (33% faster)
```

### 4.2 Model Selection

#### Complexity-Based Selection

| Complexity | Indicators | Model | Cost/M |
|------------|------------|-------|--------|
| **Simple** | Single file, <100 lines, clear spec | Haiku | $0.25/$1.25 |
| **Medium** | 1-3 files, 100-500 lines, standard patterns | Sonnet | $3/$15 |
| **Complex** | 4+ files, architecture decisions, debugging | Opus | $15/$75 |

#### Auto-Detection Heuristics

```python
def estimate_complexity(story: Story) -> str:
    score = 0

    # File scope
    if len(story.file_scope) == 1:
        score += 1
    elif len(story.file_scope) <= 3:
        score += 2
    else:
        score += 3

    # Acceptance criteria count
    if len(story.acceptance_criteria) <= 3:
        score += 1
    elif len(story.acceptance_criteria) <= 6:
        score += 2
    else:
        score += 3

    # Keywords
    complex_keywords = ["architect", "refactor", "debug", "security", "performance"]
    simple_keywords = ["add", "update", "fix typo", "rename"]

    title_lower = story.title.lower()
    if any(k in title_lower for k in complex_keywords):
        score += 2
    if any(k in title_lower for k in simple_keywords):
        score -= 1

    # Dependencies
    score += len(story.dependencies)

    if score <= 2:
        return "simple"
    elif score <= 5:
        return "medium"
    else:
        return "complex"

def select_model(complexity: str) -> str:
    return {
        "simple": "haiku",
        "medium": "sonnet",
        "complex": "opus"
    }[complexity]
```

#### Cost Impact Analysis

```
Example: 10 stories (3 simple, 5 medium, 2 complex)

Current (all Opus):
  10 stories × 50K tokens avg × $90/M = $45.00

Optimized (tiered):
  3 simple  × 50K × $1.50/M  = $0.23
  5 medium  × 50K × $18/M    = $4.50
  2 complex × 50K × $90/M    = $9.00
  Total: $13.73 (70% savings)
```

### 4.3 Context Management

#### File Cache

```python
class ContextCache:
    """
    Cache file contents and analysis across iterations.
    """

    def __init__(self, cache_dir: str = ".claude-loop/cache"):
        self.cache_dir = Path(cache_dir)
        self.file_cache: dict[str, CachedFile] = {}
        self.analysis_cache: dict[str, Any] = {}

    def get_file(self, path: str) -> CachedFile:
        """Get file from cache or read from disk."""
        stat = os.stat(path)
        cache_key = f"{path}:{stat.st_mtime}"

        if cache_key in self.file_cache:
            return self.file_cache[cache_key]

        content = Path(path).read_text()
        cached = CachedFile(
            path=path,
            content=content,
            hash=hashlib.md5(content.encode()).hexdigest(),
            mtime=stat.st_mtime
        )
        self.file_cache[cache_key] = cached
        return cached

    def get_changed_files(self, since: float) -> list[str]:
        """Get files modified since timestamp."""
        changed = []
        for path, cached in self.file_cache.items():
            if cached.mtime > since:
                changed.append(path)
        return changed
```

#### Prompt Compression

```python
def compress_context(
    story: Story,
    full_context: str,
    previous_iterations: list[Iteration]
) -> str:
    """
    Compress context to reduce token usage.

    Strategies:
    1. Include only files in story.file_scope
    2. Summarize previous iterations instead of full log
    3. Reference unchanged files by hash instead of content
    """

    compressed = []

    # Story-specific context only
    compressed.append(f"# Current Story: {story.id}")
    compressed.append(story.to_prompt())

    # Relevant files only
    compressed.append("# Relevant Files")
    for file_path in story.file_scope:
        content = cache.get_file(file_path).content
        compressed.append(f"## {file_path}\n```\n{content}\n```")

    # Summarized history
    if previous_iterations:
        compressed.append("# Previous Progress (Summary)")
        for iter in previous_iterations[-3:]:  # Last 3 only
            compressed.append(f"- {iter.story_id}: {iter.status}")

    return "\n\n".join(compressed)
```

**Token Savings:**
- Full context: ~50K tokens
- Compressed: ~15K tokens (70% reduction)

### 4.4 Parallel Execution

#### Worker Process

```bash
#!/bin/bash
# lib/worker.sh - Execute single story in isolation

execute_story() {
    local story_id=$1
    local model=$2
    local work_dir=$3
    local output_file=$4

    # Create isolated working directory
    mkdir -p "$work_dir"

    # Extract story-specific PRD
    extract_story_prd "$story_id" > "$work_dir/story.json"

    # Run Claude with specified model
    claude --model "$model" \
           --prompt "$(cat prompt.md)" \
           --context "$work_dir/story.json" \
           --output "$output_file" \
           --max-tokens 8000

    # Return exit code
    return $?
}
```

#### Parallel Group Executor

```bash
#!/bin/bash
# lib/parallel.sh - Execute parallel group

execute_parallel_group() {
    local group_id=$1
    shift
    local stories=("$@")

    local pids=()
    local results_dir=".claude-loop/parallel/$group_id"
    mkdir -p "$results_dir"

    echo "[PARALLEL] Starting group $group_id with ${#stories[@]} stories"

    # Launch all stories in parallel
    for story_id in "${stories[@]}"; do
        local model=$(get_model_for_story "$story_id")
        local work_dir="$results_dir/$story_id"
        local output_file="$results_dir/$story_id.result"

        echo "[PARALLEL] Launching $story_id with $model"

        execute_story "$story_id" "$model" "$work_dir" "$output_file" &
        pids+=($!)
    done

    # Wait for all to complete
    local failed=()
    for i in "${!pids[@]}"; do
        wait "${pids[$i]}"
        if [[ $? -ne 0 ]]; then
            failed+=("${stories[$i]}")
        fi
    done

    # Report results
    if [[ ${#failed[@]} -gt 0 ]]; then
        echo "[PARALLEL] Failed stories: ${failed[*]}"
        return 1
    fi

    echo "[PARALLEL] Group $group_id complete"
    return 0
}
```

### 4.5 Merge Controller

#### Git Coordination

```python
class MergeController:
    """
    Coordinate git operations across parallel workers.

    Strategies:
    - file_lock: Lock files being edited (prevents conflicts)
    - rebase: Rebase each worker's changes onto main
    - merge: Merge all worker branches
    """

    def __init__(self, strategy: str = "rebase"):
        self.strategy = strategy
        self.locks: dict[str, str] = {}  # file -> worker_id
        self.worker_branches: dict[str, str] = {}

    def acquire_files(self, worker_id: str, files: list[str]) -> bool:
        """Attempt to lock files for a worker."""
        for f in files:
            if f in self.locks and self.locks[f] != worker_id:
                return False  # Conflict

        for f in files:
            self.locks[f] = worker_id
        return True

    def merge_worker_results(self, worker_id: str) -> bool:
        """Merge worker's changes into main branch."""
        branch = self.worker_branches[worker_id]

        if self.strategy == "rebase":
            # Rebase worker branch onto current HEAD
            subprocess.run(["git", "rebase", "HEAD", branch], check=True)
            subprocess.run(["git", "merge", "--ff-only", branch], check=True)

        elif self.strategy == "merge":
            subprocess.run(["git", "merge", branch], check=True)

        # Release locks
        self.locks = {f: w for f, w in self.locks.items() if w != worker_id}
        return True
```

#### Conflict Resolution

```
Conflict Scenarios:

1. SAME FILE edited by multiple workers
   → Prevention: File locking based on story.fileScope
   → Resolution: Sequential execution for conflicting stories

2. DEPENDENT CODE changes
   → Prevention: Dependency graph ensures order
   → Resolution: Re-run dependent story after merge

3. GIT MERGE conflicts
   → Strategy: Rebase with manual resolution prompt
   → Fallback: Create conflict branch for human review
```

---

## 5. Implementation Plan

### Phase 1: Foundation (US-P01 to US-P03)

| Story | Title | Description |
|-------|-------|-------------|
| US-P01 | PRD schema extension | Add dependencies, fileScope, complexity fields |
| US-P02 | Dependency graph builder | Parse PRD, build execution plan |
| US-P03 | Model selector | Auto-detect complexity, select model |

### Phase 2: Parallel Execution (US-P04 to US-P06)

| Story | Title | Description |
|-------|-------|-------------|
| US-P04 | Worker process isolation | Execute stories in separate processes |
| US-P05 | Parallel group executor | Launch and manage parallel workers |
| US-P06 | Merge controller | Coordinate git operations |

### Phase 3: Optimization (US-P07 to US-P09)

| Story | Title | Description |
|-------|-------|-------------|
| US-P07 | File cache | Cache unchanged files across iterations |
| US-P08 | Prompt compression | Reduce context tokens per story |
| US-P09 | Metrics & dashboard | Track parallel execution performance |

---

## 6. User Stories (for prd-p3.json)

```json
{
  "project": "claude-loop-v2-parallelization",
  "branchName": "feature/parallel-execution",
  "description": "Add parallel execution and cost optimization to claude-loop",
  "userStories": [
    {
      "id": "US-P01",
      "title": "Extend PRD schema for parallelization",
      "description": "As a user, I want to specify story dependencies and file scopes so the system can identify parallelization opportunities",
      "acceptanceCriteria": [
        "Add 'dependencies' array field to story schema",
        "Add 'fileScope' array field to story schema",
        "Add 'estimatedComplexity' field (simple/medium/complex)",
        "Add 'suggestedModel' field (haiku/sonnet/opus)",
        "Add top-level 'parallelization' config object",
        "Update PRD validation to check for circular dependencies",
        "Backward compatible with existing PRDs (new fields optional)"
      ],
      "priority": 1,
      "dependencies": [],
      "fileScope": ["lib/prd-parser.sh", "lib/prd-schema.json"],
      "estimatedComplexity": "simple",
      "passes": false
    },
    {
      "id": "US-P02",
      "title": "Build dependency graph and execution plan",
      "description": "As a user, I want claude-loop to automatically identify which stories can run in parallel based on dependencies",
      "acceptanceCriteria": [
        "Create lib/dependency-graph.py with graph builder",
        "Implement topological sort for execution ordering",
        "Group independent stories into parallel batches",
        "Detect and report circular dependencies",
        "Output execution plan showing parallel groups",
        "Add --show-plan flag to display plan without executing"
      ],
      "priority": 2,
      "dependencies": ["US-P01"],
      "fileScope": ["lib/dependency-graph.py"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P03",
      "title": "Implement model selector",
      "description": "As a user, I want claude-loop to automatically select the cheapest appropriate model for each story",
      "acceptanceCriteria": [
        "Create lib/model-selector.py with complexity analyzer",
        "Implement heuristics based on file count, criteria count, keywords",
        "Support manual override via suggestedModel field",
        "Add --model-strategy flag (auto/always-opus/always-haiku)",
        "Log model selection reasoning in verbose mode",
        "Track model usage and cost savings in metrics"
      ],
      "priority": 3,
      "dependencies": ["US-P01"],
      "fileScope": ["lib/model-selector.py"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P04",
      "title": "Create worker process isolation",
      "description": "As a developer, I want each story to execute in an isolated process so parallel execution is safe",
      "acceptanceCriteria": [
        "Create lib/worker.sh for single-story execution",
        "Isolate working directory per worker",
        "Pass model selection to Claude invocation",
        "Capture stdout/stderr to worker-specific log files",
        "Return structured result (success/failure, files changed, tokens used)",
        "Handle worker timeouts gracefully"
      ],
      "priority": 4,
      "dependencies": ["US-P02", "US-P03"],
      "fileScope": ["lib/worker.sh"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P05",
      "title": "Implement parallel group executor",
      "description": "As a user, I want independent stories to execute simultaneously to reduce total runtime",
      "acceptanceCriteria": [
        "Create lib/parallel.sh with execute_parallel_group function",
        "Launch workers as background processes",
        "Wait for all workers in group to complete",
        "Collect and aggregate results from all workers",
        "Support --max-workers flag to limit parallelism",
        "Display parallel execution progress in terminal"
      ],
      "priority": 5,
      "dependencies": ["US-P04"],
      "fileScope": ["lib/parallel.sh"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P06",
      "title": "Implement merge controller",
      "description": "As a user, I want parallel workers' git changes to be safely merged without conflicts",
      "acceptanceCriteria": [
        "Create lib/merge-controller.py with file locking",
        "Implement rebase strategy for sequential merging",
        "Detect file conflicts before parallel execution",
        "Fall back to sequential for conflicting stories",
        "Create worker branches for isolation",
        "Clean up worker branches after successful merge"
      ],
      "priority": 6,
      "dependencies": ["US-P05"],
      "fileScope": ["lib/merge-controller.py"],
      "estimatedComplexity": "high",
      "passes": false
    },
    {
      "id": "US-P07",
      "title": "Add file caching layer",
      "description": "As a user, I want unchanged files to be cached so they don't consume tokens on re-read",
      "acceptanceCriteria": [
        "Create lib/context-cache.py with file cache",
        "Cache file contents with mtime-based invalidation",
        "Track file hashes for change detection",
        "Provide get_changed_files() for incremental context",
        "Add --no-cache flag to disable caching",
        "Report cache hit rate in metrics"
      ],
      "priority": 7,
      "dependencies": ["US-P04"],
      "fileScope": ["lib/context-cache.py"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P08",
      "title": "Implement prompt compression",
      "description": "As a user, I want prompts to include only relevant context to reduce token usage",
      "acceptanceCriteria": [
        "Create lib/prompt-compressor.py",
        "Filter files to story.fileScope only",
        "Summarize previous iterations instead of full history",
        "Reference unchanged files by hash (not content)",
        "Estimate token count before/after compression",
        "Add --full-context flag to disable compression"
      ],
      "priority": 8,
      "dependencies": ["US-P07"],
      "fileScope": ["lib/prompt-compressor.py"],
      "estimatedComplexity": "medium",
      "passes": false
    },
    {
      "id": "US-P09",
      "title": "Add parallel execution metrics",
      "description": "As a user, I want to see how much time and money parallelization saved",
      "acceptanceCriteria": [
        "Track parallel vs sequential estimated time",
        "Track model tier usage (haiku/sonnet/opus counts)",
        "Calculate cost savings vs all-opus baseline",
        "Report cache hit rate and token savings",
        "Add parallelization stats to HTML report",
        "Add /api/parallel-stats endpoint to dashboard"
      ],
      "priority": 9,
      "dependencies": ["US-P05", "US-P08"],
      "fileScope": ["lib/monitoring.sh", "dashboard/app.py"],
      "estimatedComplexity": "medium",
      "passes": false
    }
  ]
}
```

---

## 7. CLI Changes

### New Flags

```bash
./claude-loop.sh [existing flags] \
  --parallel              # Enable parallel execution (default: false)
  --max-workers N         # Max parallel workers (default: 3)
  --model-strategy MODE   # auto|always-opus|always-haiku (default: auto)
  --show-plan             # Show execution plan without running
  --no-cache              # Disable file caching
  --full-context          # Disable prompt compression
```

### Example Usage

```bash
# Run with parallelization enabled
./claude-loop.sh -p prd.json --parallel --max-workers 4

# Preview execution plan
./claude-loop.sh -p prd.json --parallel --show-plan

# Force cheap model for testing
./claude-loop.sh -p prd.json --model-strategy always-haiku

# Full verbose with all optimizations
./claude-loop.sh -p prd.json --parallel -v --max-workers 3
```

---

## 8. Expected Impact

### Time Savings

| Scenario | Sequential | Parallel (3 workers) | Savings |
|----------|------------|----------------------|---------|
| 3 independent stories | 18 min | 6 min | 67% |
| 6 stories (2 groups of 3) | 36 min | 12 min | 67% |
| 10 stories (mixed deps) | 60 min | 25 min | 58% |

### Cost Savings

| Scenario | All Opus | Tiered Models | Savings |
|----------|----------|---------------|---------|
| 10 stories avg | $45.00 | $13.73 | 70% |
| 20 stories avg | $90.00 | $27.46 | 70% |
| With caching | - | -30% additional | 79% total |

### Token Savings

| Optimization | Reduction |
|--------------|-----------|
| File caching | 20-30% |
| Prompt compression | 40-60% |
| Combined | 50-70% |

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Git merge conflicts | Medium | High | File locking, sequential fallback |
| Worker process failures | Medium | Medium | Retry logic, isolation |
| Model quality degradation (Haiku) | Medium | Medium | Complexity thresholds, manual override |
| Race conditions in shared state | Low | High | File locks, atomic operations |
| Increased complexity | High | Medium | Phased rollout, good defaults |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time reduction | >50% for parallelizable PRDs | Compare with sequential baseline |
| Cost reduction | >60% with model tiering | Track model usage in metrics |
| Token reduction | >40% with caching | Track cache hit rate |
| Reliability | <5% parallel-related failures | Track failure reasons |
| User adoption | Default enabled after validation | Usage metrics |

---

## 11. Open Questions

1. **Worker isolation level:** Process-level or container-level?
2. **Conflict resolution UI:** Automatic or prompt user?
3. **Model quality validation:** How to ensure Haiku/Sonnet produce acceptable output?
4. **Remote execution:** Should workers be able to run on different machines?
5. **Partial completion:** How to handle when some parallel workers fail?

---

## 12. Appendix: Execution Examples

### Example A: Fully Parallel

```
PRD: 4 independent stories (no dependencies)

Execution Plan:
  Group 1: [US-001, US-002, US-003, US-004]  ← All parallel

Timeline (3 workers):
  T+0:  Start US-001, US-002, US-003
  T+6:  US-001 done, start US-004
  T+6:  US-002 done
  T+6:  US-003 done
  T+12: US-004 done

Total: 12 min (vs 24 min sequential = 50% faster)
```

### Example B: Mixed Dependencies

```
PRD: 6 stories with dependencies
  US-001: []
  US-002: []
  US-003: [US-001]
  US-004: [US-002]
  US-005: [US-003, US-004]
  US-006: [US-005]

Execution Plan:
  Group 1: [US-001, US-002]      ← Parallel
  Group 2: [US-003, US-004]      ← Parallel (after Group 1)
  Group 3: [US-005]              ← Sequential
  Group 4: [US-006]              ← Sequential

Timeline (2 workers):
  T+0:  Start US-001, US-002
  T+6:  Both done, start US-003, US-004
  T+12: Both done, start US-005
  T+18: Done, start US-006
  T+24: Complete

Total: 24 min (vs 36 min sequential = 33% faster)
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial PRD |
