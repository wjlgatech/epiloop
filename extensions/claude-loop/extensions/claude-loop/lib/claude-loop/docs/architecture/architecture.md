# Claude-Loop Architecture

> Last Updated: 2026-01-20
> Version: 2.0 (Phase 2 Complete)

## 1. Overview

### 1.1 Purpose

Claude-loop is an autonomous coding agent that implements entire features by breaking them into story-sized chunks that fit within Claude's context window. The system uses persistent file-based memory, domain-aware experience storage, and hierarchical task delegation to maintain context across iterations and learn from past implementations.

### 1.2 Design Principles

1. **Context Window Management**: All tasks must fit within Claude's context window (~200k tokens)
2. **Persistent Memory**: File-based state allows resumability and learning across sessions
3. **Bounded Complexity**: Strict limits on delegation depth, context size, and execution time
4. **Progressive Disclosure**: Load only what's needed when it's needed (skills, docs, context)
5. **Fail-Safe Defaults**: All advanced features behind feature flags, disabled by default
6. **Local-First**: All code stays local, zero telemetry by default

### 1.3 Architecture Evolution

**Phase 1 (Foundations)**: Hooks system, learnings JSON, task decomposition, structured output
**Phase 2 Tier 1 (Skills & Daemon)**: Skills architecture, quick task mode, daemon mode, visual dashboard
**Phase 2 Tier 2 (Library Integration)**: MCP integration, multi-provider LLM, bounded delegation (current)

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Claude-Loop System                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Execution Layer                           │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  • claude-loop.sh (main orchestrator)                       │   │
│  │  • Story selector (priority-based)                          │   │
│  │  • Quality gates (tests, typecheck, lint)                   │   │
│  │  • Git workflow (atomic commits)                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Phase 2 Tier 2 Features                     │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐   │   │
│  │  │ MCP          │  │ Multi-Provider│  │ Bounded       │   │   │
│  │  │ Integration  │  │ LLM Router    │  │ Delegation    │   │   │
│  │  ├──────────────┤  ├───────────────┤  ├───────────────┤   │   │
│  │  │ • Server     │  │ • LiteLLM     │  │ • Max Depth=2 │   │   │
│  │  │   discovery  │  │ • Cost track  │  │ • Context=100k│   │   │
│  │  │ • Tool calls │  │ • Fallbacks   │  │ • Cycle check │   │   │
│  │  │ • Whitelist  │  │ • OpenAI      │  │ • Worktrees   │   │   │
│  │  │ • Security   │  │ • Anthropic   │  │ • Parallel    │   │   │
│  │  └──────────────┘  │ • Google      │  └───────────────┘   │   │
│  │                    │ • DeepSeek    │                       │   │
│  │                    └───────────────┘                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Phase 2 Tier 1 Features                     │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐   │   │
│  │  │ Skills       │  │ Quick Mode    │  │ Daemon Mode   │   │   │
│  │  │ Framework    │  │               │  │               │   │   │
│  │  ├──────────────┤  ├───────────────┤  ├───────────────┤   │   │
│  │  │ • Metadata   │  │ • No PRD      │  │ • Background  │   │   │
│  │  │ • On-demand  │  │ • Fast exec   │  │ • Task queue  │   │   │
│  │  │ • Scripts    │  │ • Auto-commit │  │ • Parallel    │   │   │
│  │  │ • Discovery  │  │ • Templates   │  │ • Notify      │   │   │
│  │  └──────────────┘  └───────────────┘  └───────────────┘   │   │
│  │                                                             │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │ Visual Dashboard (Flask + SSE)                       │  │   │
│  │  ├──────────────────────────────────────────────────────┤  │   │
│  │  │ • Live execution view    • Cost tracker             │  │   │
│  │  │ • Story status grid      • File diff viewer         │  │   │
│  │  │ • Real-time logs         • Historical runs          │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       Core Services                          │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ • Agent Registry (semantic + keyword matching)              │   │
│  │ • Experience Store (ChromaDB, domain-aware RAG)             │   │
│  │ • Monitoring & Cost Tracking                                │   │
│  │ • PRD Parser & Validation                                   │   │
│  │ • Dependency Graph Builder                                  │   │
│  │ • Model Selector (complexity-based)                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Persistent State                          │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ • prd.json           (task state machine)                   │   │
│  │ • progress.txt       (append-only learnings)                │   │
│  │ • AGENTS.md          (pattern documentation)                │   │
│  │ • .claude-loop/      (runtime data, sessions, cache)        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Phase 2 Tier 2 Component Detail

```
┌─────────────────────────────────────────────────────────────────────┐
│                   MCP (Model Context Protocol)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐         ┌───────────────────────────────┐  │
│  │ MCP Client         │         │ MCP Servers (External)        │  │
│  │ (Python asyncio)   │◄───────►│                               │  │
│  ├────────────────────┤  JSON-  │ • Filesystem (read-only)      │  │
│  │ • Server discovery │   RPC   │ • SQLite (read-only)          │  │
│  │ • Tool enumeration │         │ • Web Search                  │  │
│  │ • Call routing     │         │ • Custom servers              │  │
│  │ • Response format  │         └───────────────────────────────┘  │
│  └────────────────────┘                                             │
│          ↓                                                           │
│  ┌────────────────────┐         ┌───────────────────────────────┐  │
│  │ MCP Bridge         │         │ Security Layer                │  │
│  │ (Bash functions)   │         ├───────────────────────────────┤  │
│  ├────────────────────┤         │ • Whitelist enforcement       │  │
│  │ • mcp_init()       │────────►│ • Schema validation           │  │
│  │ • mcp_list_tools() │         │ • Read-only default           │  │
│  │ • mcp_call_tool()  │         │ • Audit logging               │  │
│  └────────────────────┘         └───────────────────────────────┘  │
│          ↓                                                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Integration Layer                                          │    │
│  │ • Prompt syntax: [use-mcp:server/tool:params]             │    │
│  │ • Context injection: MCP responses → Claude context       │    │
│  │ • Feature flag: ENABLE_MCP=false (default)                │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     Multi-Provider LLM Router                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐         ┌───────────────────────────────┐  │
│  │ Provider Selector  │         │ Provider Configuration        │  │
│  │ (lib/provider_     │         │ (lib/llm_providers.yaml)      │  │
│  │  selector.py)      │────────►├───────────────────────────────┤  │
│  ├────────────────────┤         │ Providers (10+):              │  │
│  │ Complexity scoring │         │ • Anthropic (Claude)          │  │
│  │ • <3: Haiku/GPT-4o │         │ • OpenAI (GPT-4o, O1)         │  │
│  │ • 3-5: Sonnet/GPT  │         │ • Google (Gemini)             │  │
│  │ • >5: Opus/O1      │         │ • DeepSeek (V3, R1)           │  │
│  ├────────────────────┤         │                               │  │
│  │ Capability filter  │         │ Metadata per provider:        │  │
│  │ • Vision required? │         │ • cost_per_1k_input           │  │
│  │ • Tools required?  │         │ • cost_per_1k_output          │  │
│  └────────────────────┘         │ • capabilities (vision,tools) │  │
│          ↓                       │ • enabled (true/false)        │  │
│  ┌────────────────────┐         └───────────────────────────────┘  │
│  │ LiteLLM Wrapper    │                                             │
│  │ (unified interface)│         ┌───────────────────────────────┐  │
│  ├────────────────────┤         │ Fallback Chain                │  │
│  │ • Model routing    │────────►│ 1. Primary (cheapest capable) │  │
│  │ • Error handling   │         │ 2. Secondary (next best)      │  │
│  │ • Rate limit retry │         │ 3. Claude fallback (always OK)│  │
│  └────────────────────┘         └───────────────────────────────┘  │
│          ↓                                                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Cost Tracking                                              │    │
│  │ • provider_usage.jsonl (per-iteration logging)             │    │
│  │ • Cost report: ./claude-loop.sh --cost-report              │    │
│  │ • Expected savings: 30-50% (70%+ for simple tasks)         │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        Bounded Delegation                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐         ┌───────────────────────────────┐  │
│  │ Delegation Parser  │         │ Limits (Strictly Enforced)    │  │
│  │ (bash)             │         ├───────────────────────────────┤  │
│  ├────────────────────┤         │ • MAX_DELEGATION_DEPTH=2      │  │
│  │ Syntax:            │────────►│ • MAX_CONTEXT_PER_AGENT=100k  │  │
│  │ [delegate:         │         │ • Cycle detection (DAG only)  │  │
│  │  description:      │         │ • Timeout per subtask: 5min   │  │
│  │  estimated_hours]  │         └───────────────────────────────┘  │
│  └────────────────────┘                                             │
│          ↓                                                           │
│  ┌────────────────────┐         ┌───────────────────────────────┐  │
│  │ Delegation Tracker │         │ Git Worktree Isolation        │  │
│  │ (Python)           │         ├───────────────────────────────┤  │
│  ├────────────────────┤         │ Each subtask:                 │  │
│  │ • Hierarchy tree   │────────►│ • Own worktree branch         │  │
│  │ • Cycle detection  │         │ • Isolated workspace          │  │
│  │ • Cost attribution │         │ • Parallel execution capable  │  │
│  │ • delegation.jsonl │         │ • Merge back to parent        │  │
│  └────────────────────┘         └───────────────────────────────┘  │
│          ↓                                                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Execution Flow                                             │    │
│  │ 1. Parse delegation request from LLM response              │    │
│  │ 2. Validate: depth < 2, context < 100k, no cycles         │    │
│  │ 3. Create child worktree (git worktree add)                │    │
│  │ 4. Execute subtask (run worker.sh in child)                │    │
│  │ 5. Capture results, inject into parent context            │    │
│  │ 6. Merge back (git rebase + merge)                         │    │
│  │ 7. Track costs (attribute child costs to parent)           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow

### 3.1 Standard Execution Flow (No Delegation)

```
1. Read State
   ├─ prd.json (task state machine)
   ├─ progress.txt (learnings from past iterations)
   └─ AGENTS.md (codebase patterns)

2. Select Story
   └─ Highest priority incomplete story (priority = lowest number)

3. [Phase 2 Tier 2] Select Provider
   ├─ Analyze story complexity (0-10)
   ├─ Check required capabilities (vision, tools)
   ├─ Select cheapest capable provider via LiteLLM
   └─ Fallback chain: primary → secondary → Claude

4. [Phase 2 Tier 2] Initialize MCP (if enabled)
   ├─ Connect to configured MCP servers
   ├─ Discover available tools
   └─ Load whitelist and security policies

5. Load Agents
   ├─ Semantic matching (story description → agent expertise)
   ├─ Keyword matching (story keywords → agent triggers)
   └─ Select top 2 agents by relevance score

6. Retrieve Experience
   ├─ Detect domain (web, unity, ml, physical)
   ├─ Query ChromaDB vector store (domain-partitioned)
   └─ Inject top 3 similar problem-solutions into context

7. Build Prompt
   ├─ Story description + acceptance criteria
   ├─ Relevant files (fileScope if specified)
   ├─ Agent instructions (top 2 agents)
   ├─ Experience context (similar solutions)
   └─ [Phase 2 Tier 2] MCP tool availability

8. Execute Story
   ├─ Call selected LLM provider (via LiteLLM or Claude CLI)
   ├─ [Phase 2 Tier 2] MCP tool calls (if [use-mcp:...] in response)
   ├─ [Phase 2 Tier 2] Delegation requests (if [delegate:...] in response)
   ├─ Parse structured JSON response
   └─ Extract files changed, tests run, completion status

9. Validate Quality
   ├─ Tests pass (pytest/jest/cargo test)
   ├─ Typecheck passes (mypy/tsc/cargo check)
   └─ Linter passes (pylint/eslint/clippy)

10. Commit Changes
    ├─ Atomic git commit with story ID
    └─ Descriptive message with AC met

11. Update State
    ├─ Set story.passes = true in prd.json
    ├─ Append learnings to progress.txt
    └─ [Phase 2 Tier 2] Log provider usage, MCP calls, delegations

12. Record Experience
    ├─ Extract problem-solution pair
    ├─ Tag with domain
    └─ Store in ChromaDB for future retrieval

13. Check Completion
    ├─ All stories.passes == true? → <loop>COMPLETE</loop>
    └─ Else → Continue with next story
```

### 3.2 Delegation Execution Flow (Phase 2 Tier 2)

```
[Parent Story Executing...]

1. Detect Delegation Request
   └─ LLM response contains [delegate:description:hours]

2. Validate Delegation
   ├─ Check depth: current_depth + 1 <= MAX_DELEGATION_DEPTH (2)
   ├─ Check context: estimated_context < MAX_CONTEXT_PER_AGENT (100k)
   └─ Check cycles: subtask not in delegation ancestry chain

3. Create Child Execution
   ├─ Create git worktree: worker/child_US-XXX_timestamp
   ├─ Set environment: DELEGATION_DEPTH=$((parent_depth + 1))
   ├─ Generate child PRD (single story from delegation description)
   └─ Set DELEGATION_PARENT_ID=parent_story_id

4. Execute Child (Parallel Capable)
   ├─ Run worker.sh in child worktree
   ├─ Child follows standard execution flow (steps 1-11 above)
   ├─ Child can delegate further if depth allows (recursive)
   └─ Child records costs separately

5. Capture Child Results
   ├─ Read child worker.sh output (JSON)
   ├─ Extract: files_changed, tests_passed, completion_status
   └─ Summarize child execution for parent context

6. Inject Results into Parent
   ├─ Append child summary to parent context
   ├─ Include: what was done, files changed, key learnings
   └─ Parent LLM sees child results in next iteration

7. Merge Child Branch
   ├─ Rebase child branch onto parent branch
   ├─ Merge child commits into parent
   └─ Clean up child worktree

8. Attribute Costs
   ├─ Child costs → add to parent story total
   ├─ Track delegation overhead (coordination cost)
   └─ Report in delegation.jsonl and cost report

9. Continue Parent Execution
   └─ Parent proceeds with child results in context
```

### 3.3 MCP Tool Call Flow (Phase 2 Tier 2)

```
[Story Executing with MCP Enabled...]

1. LLM Response Contains MCP Call
   └─ Example: [use-mcp:filesystem/read_file:{"path": "src/main.py"}]

2. Parse MCP Syntax
   ├─ Extract: server_name = "filesystem"
   ├─ Extract: tool_name = "read_file"
   └─ Extract: params = {"path": "src/main.py"}

3. Validate MCP Call
   ├─ Check server is configured and connected
   ├─ Check tool is in whitelist (security)
   └─ Validate params against tool schema

4. Execute MCP Tool
   ├─ Call mcp_client.py invoke <server> <tool> <params>
   ├─ MCP client sends JSON-RPC request to server
   ├─ Server executes tool (filesystem read, database query, etc.)
   └─ Server returns result (JSON)

5. Format MCP Response
   ├─ Convert MCP JSON to Claude-compatible format
   ├─ Add metadata: tool used, execution time, success/failure
   └─ Log call to .claude-loop/logs/mcp_calls.jsonl

6. Inject into Context
   ├─ Append MCP result to current context
   ├─ LLM sees result in same iteration
   └─ LLM can make follow-up MCP calls or continue implementation

7. Error Handling
   ├─ MCP server unavailable → log warning, continue without tool
   ├─ Tool not whitelisted → return error, suggest whitelisting
   ├─ Tool execution failed → return error details to LLM
   └─ Timeout (5s) → abort call, log timeout
```

---

## 4. Component Responsibilities

### 4.1 Core Components

| Component | Responsibility | Technology | Phase |
|-----------|----------------|------------|-------|
| `claude-loop.sh` | Main orchestrator, story execution loop | Bash | 1 |
| `lib/prd-parser.sh` | PRD validation, story queries, dependency graph | Bash + jq | 1 |
| `lib/monitoring.sh` | Cost tracking, metrics collection, JSON logging | Bash | 1 |
| `lib/agent-registry.sh` | Agent discovery, semantic matching | Bash + Python | 1 |
| `lib/experience-store.py` | ChromaDB vector storage, domain-aware RAG | Python | 1 |
| `lib/worker.sh` | Isolated story execution in separate workspace | Bash | 1 |
| `lib/parallel.sh` | Parallel batch execution, progress tracking | Bash | 1 |

### 4.2 Phase 2 Tier 1 Components

| Component | Responsibility | Technology | Phase |
|-----------|----------------|------------|-------|
| `lib/skills-framework.sh` | Skills discovery, on-demand loading, execution | Bash | 2.1 |
| `lib/quick-task-mode.sh` | No-PRD execution, fast task completion | Bash | 2.1 |
| `lib/daemon.sh` | Background execution, task queue management | Bash | 2.1 |
| `lib/notifications.sh` | Email/Slack/webhook notifications | Bash | 2.1 |
| `lib/dashboard/server.py` | Flask REST API, SSE streaming | Python | 2.1 |
| `lib/dashboard/static/` | Web UI (HTML/CSS/JS), real-time visualization | Vanilla JS | 2.1 |

### 4.3 Phase 2 Tier 2 Components (New)

| Component | Responsibility | Technology | Phase |
|-----------|----------------|------------|-------|
| `lib/mcp_client.py` | MCP protocol client, server connections | Python (asyncio) | 2.2 |
| `lib/mcp_bridge.sh` | Bash bridge for MCP calls from prompt | Bash | 2.2 |
| `lib/provider_selector.py` | Complexity-based provider selection | Python | 2.2 |
| `lib/cost_report.py` | Cost tracking, savings analysis | Python | 2.2 |
| `lib/delegation_parser.sh` | Parse delegation syntax from LLM | Bash | 2.2 |
| `lib/delegation_tracker.py` | Hierarchy tracking, cycle detection | Python | 2.2 |
| `lib/delegation.sh` | Delegation orchestration, worktree management | Bash | 2.2 |

### 4.4 Configuration Files

| File | Purpose | Format | Phase |
|------|---------|--------|-------|
| `prd.json` | Task state machine, user stories | JSON | 1 |
| `progress.txt` | Append-only learnings log | Markdown | 1 |
| `AGENTS.md` | Pattern documentation | Markdown | 1 |
| `config.yaml` | Quality gates, execution settings | YAML | 1 |
| `.claude-loop/mcp-config.json` | MCP server endpoints, whitelists | JSON | 2.2 |
| `lib/llm_providers.yaml` | Provider configuration, costs, capabilities | YAML | 2.2 |
| `.claude-loop/session-state.json` | Current session checkpoint | JSON | 1 |

---

## 5. Security Architecture

### 5.1 MCP Security Model

**Principle**: Whitelist-only, read-only default, explicit approval for write operations.

- **Server Whitelist**: Only configured MCP servers can be used
- **Tool Whitelist**: Only whitelisted tools per server can be invoked
- **Schema Validation**: All tool parameters validated against MCP schemas
- **Read-Only Default**: Filesystem and database tools are read-only by default
- **Write Approval**: Write operations require user approval or separate whitelist
- **Audit Logging**: All MCP calls logged to `.claude-loop/logs/mcp_calls.jsonl`

**Example Configuration**:
```json
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "http://localhost:8080",
      "auth_type": "none",
      "enabled": true,
      "tools_whitelist": ["read_file", "list_directory"],  // No write_file
      "readonly": true
    }
  ]
}
```

### 5.2 Delegation Security Model

**Principle**: Bounded complexity, prevent runaway execution.

- **Depth Limit**: MAX_DELEGATION_DEPTH=2 (parent → child → grandchild, no further)
- **Context Limit**: MAX_CONTEXT_PER_AGENT=100k tokens (prevent context explosion)
- **Cycle Detection**: DAG-only delegation graph (A→B→A blocked)
- **Timeout Protection**: Each subtask has 5-minute timeout
- **Cost Attribution**: Child costs attributed to parent (prevent cost hiding)
- **Workspace Isolation**: Git worktrees provide filesystem isolation

### 5.3 Multi-Provider Security

**Principle**: Secure API key management, fail-safe fallbacks.

- **Environment Variables**: API keys in env vars, never in config files
- **No Key Logging**: API keys never logged or displayed
- **Fallback to Claude**: If all providers fail, fallback to Claude CLI (always available)
- **Rate Limit Handling**: Automatic retry with exponential backoff
- **Provider Validation**: Only known providers allowed (no arbitrary LLM endpoints)

---

## 6. Performance Characteristics

### 6.1 Latency Targets

| Operation | Target Latency | Actual (Phase 2.2) |
|-----------|----------------|--------------------|
| PRD validation | < 500ms | ~200ms (optimized) |
| Story selection | < 100ms | ~50ms |
| Provider selection | < 50ms | ~1ms |
| MCP tool call (local) | < 500ms | ~200-400ms |
| MCP tool call (remote) | < 2s | ~1-1.5s |
| Delegation creation | < 2s | ~1-1.5s |
| Quality gates | < 30s | ~15-25s |

### 6.2 Cost Savings (Phase 2 Tier 2)

| Scenario | Phase 1 (Opus only) | Phase 2.2 (Multi-Provider) | Savings |
|----------|---------------------|----------------------------|---------|
| Simple task (complexity < 3) | $1.50 | $0.15 (Haiku) | 90% |
| Medium task (complexity 3-5) | $3.00 | $1.20 (Sonnet) | 60% |
| Complex task (complexity > 5) | $5.00 | $4.50 (Opus fallback) | 10% |
| **Mixed workload (typical)** | **$10.00** | **$3.50** | **65%** |

**Expected Overall Savings**: 30-50% on diverse workloads, 70%+ on simple tasks.

### 6.3 Delegation Overhead

| Metric | No Delegation | With Delegation (depth=1) | Overhead |
|--------|---------------|---------------------------|----------|
| Execution time | 60s | 70s | +16% |
| Token usage | 50k | 55k | +10% |
| Cost | $2.50 | $2.75 | +10% |

**Delegation is beneficial when**: Parallelization speedup > overhead (typically for complex tasks with 3+ subtasks).

---

## 7. Monitoring and Observability

### 7.1 Metrics Collected

**Execution Metrics**:
- Total runtime (ms)
- Stories completed / total
- Success rate (%)
- Cost per story (USD)
- Tokens per story (input + output)

**Phase 2 Tier 2 Metrics**:
- Provider usage distribution (Haiku/Sonnet/Opus/etc.)
- Provider fallback rate (%)
- MCP call count, latency, success rate
- Delegation frequency, depth distribution
- Cost savings vs Phase 1 baseline

### 7.2 Logging Locations

| Log File | Content | Format |
|----------|---------|--------|
| `.claude-loop/runs/{timestamp}/metrics.json` | Per-iteration metrics | JSON |
| `.claude-loop/runs/{timestamp}/summary.json` | Run summary | JSON |
| `.claude-loop/logs/provider_usage.jsonl` | Provider selection, costs | JSONL |
| `.claude-loop/logs/mcp_calls.jsonl` | MCP tool calls, latency | JSONL |
| `.claude-loop/logs/delegation.jsonl` | Delegation hierarchy, costs | JSONL |
| `.claude-loop/workers/{story}/logs/combined.log` | Worker execution logs | Text |

### 7.3 Dashboard API Endpoints

| Endpoint | Purpose | SSE Streaming |
|----------|---------|---------------|
| `/api/status` | Current execution status | No |
| `/api/stories` | Story status grid | No |
| `/api/logs` | Execution logs | No |
| `/api/metrics` | Run metrics | No |
| `/api/stream` | Real-time updates | Yes (SSE) |
| `/api/history` | Historical runs | No |
| `/api/cost-report` | Cost analysis | No |
| `/api/delegation-tree` | Delegation visualization | No |

---

## 8. Deployment Architecture

### 8.1 Local Development

**Standard Setup**:
```bash
# Install dependencies
brew install jq python3 git bc curl  # macOS
pip3 install -r requirements.txt

# Configure API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."  # For multi-provider
export GOOGLE_API_KEY="..."     # For Gemini

# Run claude-loop
./claude-loop.sh prd.json
```

### 8.2 Daemon Mode (Background Execution)

```bash
# Start daemon
./claude-loop.sh daemon start

# Submit tasks to queue
./claude-loop.sh daemon submit prd.json --priority high --notify email

# Monitor via dashboard
./claude-loop.sh dashboard start
# Open http://localhost:8080

# Stop daemon
./claude-loop.sh daemon stop
```

### 8.3 Phase 2 Tier 2 Setup

**Enable MCP**:
```bash
# Install MCP servers
npx @modelcontextprotocol/server-filesystem /path/to/codebase &

# Configure MCP
cp .claude-loop/mcp-config.example.json .claude-loop/mcp-config.json
# Edit mcp-config.json with your server endpoints

# Run with MCP enabled
./claude-loop.sh --enable-mcp prd.json
```

**Enable Multi-Provider**:
```bash
# Configure providers
cp lib/llm_providers.example.yaml lib/llm_providers.yaml
# Edit llm_providers.yaml with your API keys and costs

# Run with multi-provider enabled
./claude-loop.sh --enable-multi-provider prd.json

# View cost report
./claude-loop.sh --cost-report
```

**Enable Delegation**:
```bash
# Run with delegation enabled (experimental)
./claude-loop.sh --enable-delegation prd.json

# View delegation tree
python3 lib/delegation_visualizer.py show
```

---

## 9. Related Documents

- **Feature Documentation**:
  - [MCP Integration](../features/mcp-integration.md)
  - [Multi-Provider LLM](../features/multi-provider-llm.md)
  - [Bounded Delegation](../features/bounded-delegation.md)
  - [Skills Architecture](../features/skills-architecture.md)
  - [Quick Task Mode](../features/quick-task-mode.md)
  - [Daemon Mode](../features/daemon-mode.md)

- **Migration Guides**:
  - [Phase 1 to Phase 2 Tier 1](../MIGRATION-PHASE2.md)
  - [Phase 2 Tier 1 to Tier 2](../MIGRATION_TIER2.md)

- **Operations**:
  - [Troubleshooting Guide](../TROUBLESHOOTING.md)
  - [Performance Audit](../audits/performance-audit.md)
  - [Security Audit](../audits/security-audit.md)

- **Development**:
  - [AGENTS.md](../../AGENTS.md) - Pattern documentation
  - [CONTRIBUTING.md](../../CONTRIBUTING.md) - Development guidelines

---

*This document is maintained as the architecture evolves. Last major update: Phase 2 Tier 2 Integration (2026-01-20).*
