# Bounded Delegation Design

**Date:** 2026-01-20
**Story:** US-007 - Implement Bounded Delegation (Max Depth=2)
**Complexity:** High (24 estimated hours)

## Overview

Hierarchical task delegation for complex stories with strict safety bounds. An agent can delegate subtasks to subordinate agents up to a maximum depth of 2, with context budget limits and cycle detection to prevent runaway execution.

**Key Safety Constraints:**
- MAX_DELEGATION_DEPTH=2 (hard maximum=3 configurable)
- MAX_CONTEXT_PER_AGENT=100k tokens
- Cycle detection (prevent A→B→A loops)
- Feature flag: ENABLE_DELEGATION=false by default

## Design Decisions

### Architecture Approach

After analyzing the requirements and existing infrastructure, I'm recommending:

**Approach 1: Git Worktree-Based Isolation (Recommended)**

Leverage existing git worktree infrastructure from lib/worker.sh for parallel execution:

**Pros:**
- Complete filesystem isolation per subordinate
- Proven pattern already in use (lib/worker.sh)
- Natural parent-child relationship via worktree hierarchy
- Easy to debug (each agent has dedicated directory)
- Clean rollback on failure

**Cons:**
- Git worktree overhead (~100-200ms per worktree)
- Disk space usage (minimal for code-only)

**Alternative Approach 2: In-Process Execution (Rejected)**

Execute subordinates as nested function calls within same process:

**Pros:**
- Faster (no process spawning)
- Simpler implementation

**Cons:**
- No filesystem isolation (conflicts on file writes)
- Harder to enforce context limits
- Risk of state pollution between agents
- Difficult to debug nested failures

**Decision: Approach 1** - Worktree isolation is the right tradeoff for safety and debuggability.

## Architecture

### Component Structure

```
lib/
├── delegation.sh           # Core delegation functions
├── delegation-parser.sh    # Parse [delegate:...] syntax
├── delegation-tracker.sh   # Hierarchy tracking and cycle detection
└── worker.sh              # Existing worker (enhanced for delegation)

.claude-loop/
├── logs/
│   └── delegation.jsonl   # Delegation hierarchy log
└── delegation/
    ├── depth_tracker.json # Current depth per agent
    └── cycle_detector.json # Execution graph for cycle detection
```

### Key Components

**1. Delegation Parser (delegation-parser.sh)**

Parses delegation syntax from LLM response:
```
[delegate:subtask_description:estimated_hours]
```

Returns:
- subtask_description (string)
- estimated_hours (integer)
- parent_story_id (from environment)

**2. Delegation Tracker (delegation-tracker.sh)**

Tracks delegation hierarchy and detects cycles:
- Maintains execution graph: parent_id → [child_ids]
- Validates depth before delegation
- Detects cycles using DFS
- Logs delegation events to delegation.jsonl

**3. Delegation Executor (delegation.sh)**

Orchestrates subordinate execution:
- Creates child worktree
- Sets DELEGATION_DEPTH=$((parent_depth+1))
- Enforces context budget (MAX_CONTEXT_PER_AGENT)
- Executes child story via worker.sh
- Captures and summarizes results
- Injects results into parent context
- Cleans up worktree after completion

**4. Worker Enhancement (worker.sh)**

Extended to support delegation:
- Read DELEGATION_DEPTH from environment
- Check depth limit before execution
- Provide delegation context to Claude
- Return structured results for parent injection

## Data Flow

### Delegation Flow

```
1. Parent Agent Execution
   ├── Reads story from PRD
   ├── Generates plan with [delegate:...] syntax
   └── Calls delegation-parser.sh

2. Validation Phase
   ├── delegation-tracker.sh: Check current depth
   ├── Validate depth < MAX_DELEGATION_DEPTH (2)
   ├── delegation-tracker.sh: Check for cycles
   ├── Calculate context budget remaining
   └── Abort if any limit would be exceeded

3. Subordinate Execution
   ├── delegation.sh: Create child worktree
   ├── delegation.sh: Set DELEGATION_DEPTH=$((parent+1))
   ├── delegation.sh: Create child story entry in PRD
   ├── worker.sh: Execute child story
   ├── Capture: success/failure, files_changed, output
   └── delegation.sh: Cleanup child worktree

4. Result Integration
   ├── Summarize child results (limit to 2k tokens)
   ├── Inject into parent context
   ├── Log delegation event
   └── Update parent story with child outcomes

5. Cost Attribution
   ├── Track child costs separately
   ├── Aggregate into parent story total
   └── Include in cost report with hierarchy
```

### Cycle Detection Algorithm

Uses DFS (Depth-First Search) to detect cycles:

```python
def detect_cycle(execution_graph, new_edge_parent, new_edge_child):
    # Would adding this edge create a cycle?
    visited = set()

    def dfs(node):
        if node in visited:
            return True  # Cycle detected
        visited.add(node)
        for child in execution_graph.get(node, []):
            if dfs(child):
                return True
        visited.remove(node)
        return False

    # Temporarily add edge and check
    execution_graph[new_edge_parent].append(new_edge_child)
    has_cycle = dfs(new_edge_parent)
    execution_graph[new_edge_parent].remove(new_edge_child)

    return has_cycle
```

### Context Budget Enforcement

```bash
calculate_context_budget() {
    local parent_context_tokens="$1"
    local child_estimate_tokens="$2"
    local max_context="$MAX_CONTEXT_PER_AGENT"  # 100k

    local remaining=$((max_context - parent_context_tokens))

    if (( child_estimate_tokens > remaining )); then
        echo "ERROR: Child task estimated at ${child_estimate_tokens} tokens"
        echo "Remaining budget: ${remaining} tokens"
        echo "Simplify subtask or increase parent efficiency"
        return 1
    fi

    return 0
}
```

## Delegation Syntax

### In Prompts (Instruction to Claude)

```markdown
You can delegate complex subtasks using this syntax:
[delegate:subtask_description:estimated_hours]

Example:
[delegate:Implement JWT token generation and validation:4]
[delegate:Create login UI component with form validation:3]
[delegate:Write integration tests for auth flow:2]

Constraints:
- Maximum delegation depth: 2 (you are at depth 0)
- Each subtask must be independently completable
- Estimated hours guide complexity selection
```

### In LLM Response (Claude's Output)

```
I'll break this authentication feature into 3 subtasks:

[delegate:Implement JWT token generation and validation:4]
[delegate:Create login UI component with form validation:3]
[delegate:Write integration tests for auth flow:2]

Each subtask will run in parallel and report back results.
```

### Parsed Result

```json
{
  "delegations": [
    {
      "description": "Implement JWT token generation and validation",
      "estimated_hours": 4,
      "parent_story_id": "US-007",
      "child_story_id": "US-007-DEL-001",
      "depth": 1
    },
    {
      "description": "Create login UI component with form validation",
      "estimated_hours": 3,
      "parent_story_id": "US-007",
      "child_story_id": "US-007-DEL-002",
      "depth": 1
    },
    {
      "description": "Write integration tests for auth flow",
      "estimated_hours": 2,
      "parent_story_id": "US-007",
      "child_story_id": "US-007-DEL-003",
      "depth": 1
    }
  ]
}
```

## Logging Format

### delegation.jsonl

```json
{
  "timestamp": "2026-01-20T10:30:45Z",
  "parent_story": "US-007",
  "child_story": "US-007-DEL-001",
  "depth": 1,
  "parent_id": "exec-12345",
  "child_id": "exec-12346",
  "description": "Implement JWT token generation",
  "status": "started",
  "worktree_path": ".claude-loop/workers/US-007-DEL-001_20260120_103045"
}

{
  "timestamp": "2026-01-20T10:35:22Z",
  "parent_story": "US-007",
  "child_story": "US-007-DEL-001",
  "depth": 1,
  "parent_id": "exec-12345",
  "child_id": "exec-12346",
  "status": "completed",
  "duration_ms": 277000,
  "tokens_in": 12500,
  "tokens_out": 3200,
  "cost_usd": 0.45,
  "files_changed": ["lib/jwt.py", "tests/test_jwt.py"],
  "success": true
}
```

## Error Handling

### Depth Limit Exceeded

```
ERROR: Delegation depth limit (2) reached. Cannot delegate further.

Current depth: 2
Attempted delegation: Implement advanced caching layer
Suggestion: Complete this task at current level or simplify.
```

### Context Budget Exceeded

```
ERROR: Agent context budget (100k tokens) exceeded. Simplify subtask.

Current context: 85,000 tokens
Subtask estimate: 35,000 tokens
Total would be: 120,000 tokens
Maximum allowed: 100,000 tokens

Suggestion: Break subtask into smaller pieces or reduce parent context.
```

### Cycle Detected

```
ERROR: Delegation cycle detected. Cannot delegate to avoid infinite loop.

Cycle path: US-007 → US-007-DEL-001 → US-007 (attempted)

This would create an infinite delegation loop.
```

### Worktree Creation Failed

```
ERROR: Failed to create child worktree for delegation.

Child story: US-007-DEL-001
Worktree path: .claude-loop/workers/US-007-DEL-001_20260120_103045
Git error: worktree already exists

Action: Cleanup old worktrees and retry
Command: git worktree prune
```

## Testing Strategy

### Unit Tests

**delegation-parser_test.sh:**
- Parse valid delegation syntax
- Handle malformed syntax
- Extract description and estimated hours
- Generate unique child story IDs

**delegation-tracker_test.sh:**
- Depth tracking (0→1→2, reject at 3)
- Cycle detection (A→B→A rejection)
- Concurrent delegation tracking
- Log format validation

**delegation_test.sh:**
- Context budget enforcement
- Worktree creation and cleanup
- Result summarization and injection
- Cost attribution to parent

### Integration Tests

**delegation_integration_test.sh:**
1. Simple delegation (depth 0→1)
2. Two-level delegation (depth 0→1→2)
3. Depth limit rejection (depth 2→3 blocked)
4. Cycle rejection (A→B→A blocked)
5. Context budget rejection
6. Parallel delegation (3 subtasks at depth 1)
7. Cost attribution across hierarchy
8. Failure handling (child fails, parent continues)

### Performance Tests

- Delegation overhead: <200ms per delegation
- Worktree creation: <150ms
- Cycle detection: O(N) where N=total delegations
- Context budget calculation: <10ms

## Security Considerations

### Hard Limits Enforcement

```bash
# CRITICAL: These limits MUST be enforced
MAX_DELEGATION_DEPTH=2  # Configurable, hard maximum=3
MAX_CONTEXT_PER_AGENT=100000  # 100k tokens
MAX_DELEGATIONS_PER_STORY=10  # Prevent delegation explosion
```

### Worktree Isolation

- Each subordinate executes in isolated git worktree
- No shared filesystem state between agents
- Parent cannot access child files until merge
- Child cannot access parent files

### Resource Limits

- Delegation timeout: 30 minutes per subordinate
- Total delegation time: 2 hours per parent
- Memory limit: Inherited from system (ulimit)

## Rollout Plan

### Phase 1: Core Implementation (Days 1-3)

- Implement delegation-parser.sh
- Implement delegation-tracker.sh with cycle detection
- Implement delegation.sh executor
- Enhance worker.sh for delegation support

### Phase 2: Integration (Days 4-5)

- Integrate into claude-loop.sh
- Add feature flag: --enable-delegation
- Add CLI commands: --delegation-status, --delegation-tree
- Implement cost attribution

### Phase 3: Testing (Days 6-7)

- Unit tests for each component
- Integration tests for full flow
- Performance benchmarking
- Security validation

### Phase 4: Documentation (Day 8)

- docs/features/bounded-delegation.md
- Example PRDs with delegation
- Troubleshooting guide
- Update main README.md

## Implementation Checklist

- [ ] Create lib/delegation-parser.sh with syntax parser
- [ ] Create lib/delegation-tracker.sh with cycle detection
- [ ] Create lib/delegation.sh with executor
- [ ] Enhance lib/worker.sh for DELEGATION_DEPTH
- [ ] Add delegation logging to .claude-loop/logs/delegation.jsonl
- [ ] Integrate [delegate:...] parsing into claude-loop.sh
- [ ] Add feature flag: ENABLE_DELEGATION (default: false)
- [ ] Implement context budget enforcement
- [ ] Implement depth limit enforcement
- [ ] Implement cycle detection
- [ ] Add cost attribution to parent
- [ ] Create tests/delegation_test.sh
- [ ] Create tests/delegation_integration_test.sh
- [ ] Write docs/features/bounded-delegation.md
- [ ] Add example PRD: prds/examples/delegation-example.json
- [ ] Update README.md with delegation feature

## Success Criteria

✓ All 15 acceptance criteria from US-007 met
✓ Depth limit strictly enforced (max=2)
✓ Context budget strictly enforced (100k)
✓ Cycle detection prevents infinite loops
✓ Parallel delegation via worktrees functional
✓ Cost tracking attributes child costs to parent
✓ Clear error messages for all failure modes
✓ Integration tests achieving >95% coverage
✓ Documentation comprehensive and clear
✓ Feature flag enables safe rollback

## References

- agent-zero's call_subordinate: `python/tools/call_subordinate.py`
- Existing worker infrastructure: `lib/worker.sh`
- Parallel execution patterns: `lib/parallel.sh`
- PRD specification: US-007 in `prds/phase2-tier2-library-integration.json`
