# Phase 2 Tier 2 Library Integration - Migration Guide

## Overview

This guide covers the migration to Phase 2 Tier 2 Library Integration, which introduces three major capabilities:

1. **MCP (Model Context Protocol)** - Access to community tool ecosystem
2. **Multi-Provider LLM** - Cost optimization through intelligent provider routing
3. **Bounded Delegation** - Hierarchical task decomposition (max depth=2)

**Timeline:** 12 weeks (US-005 through US-010)
**Branch:** `feature/tier2-library-integration`
**Status:** Implementation complete, validation in progress

---

## Prerequisites

### Phase 1 Requirements

Before migrating to Phase 2 Tier 2, ensure you have:

- ✅ Claude-loop Phase 1 installed and working
- ✅ Python 3.9+ with pip
- ✅ Git 2.30+ (for worktree support)
- ✅ jq 1.6+ for JSON processing
- ✅ Active API keys for providers you want to use

### New Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# New dependencies added:
# - mcp==1.13.1 (Model Context Protocol)
# - litellm (Multi-provider LLM support)

# Verify installations
python3 -c "import mcp; print(f'MCP version: {mcp.__version__}')"
python3 -c "import litellm; print('LiteLLM installed successfully')"
```

### API Keys Required

```bash
# Set up API keys for providers you want to use
export ANTHROPIC_API_KEY="sk-ant-..."  # Required for Claude (default)
export OPENAI_API_KEY="sk-..."          # Optional for GPT models
export GOOGLE_API_KEY="..."             # Optional for Gemini
export DEEPSEEK_API_KEY="..."           # Optional for DeepSeek

# Add to your shell profile for persistence
echo 'export ANTHROPIC_API_KEY="..."' >> ~/.bashrc  # or ~/.zshrc
```

---

## Feature 1: MCP Integration (US-005)

### What is MCP?

MCP (Model Context Protocol) provides access to a growing ecosystem of community-built tools for databases, filesystems, APIs, and cloud services. Instead of building every tool from scratch, you can leverage pre-built MCP servers.

### Enabling MCP

```bash
# Enable MCP feature
export ENABLE_MCP=true

# Or use command-line flag (future)
./claude-loop.sh --enable-mcp --prd prd.json
```

### Configuration

Create `.claude-loop/mcp-config.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "@modelcontextprotocol/server-filesystem",
      "auth_type": "none",
      "enabled": true,
      "tools_whitelist": [
        "read_file",
        "read_directory",
        "list_directory"
      ],
      "config": {
        "readonly": true,
        "allowed_directories": ["/src", "/docs"]
      }
    },
    {
      "name": "sqlite",
      "endpoint": "@modelcontextprotocol/server-sqlite",
      "auth_type": "none",
      "enabled": true,
      "tools_whitelist": [
        "query",
        "list_tables",
        "describe_table"
      ],
      "config": {
        "readonly": true,
        "database": "app.db"
      }
    },
    {
      "name": "web-search",
      "endpoint": "custom-web-search-server",
      "auth_type": "bearer",
      "enabled": false,
      "tools_whitelist": ["search"],
      "config": {
        "api_key": "${WEB_SEARCH_API_KEY}"
      }
    }
  ]
}
```

### Using MCP Tools

**In prompts (future):**
```markdown
I need to analyze the codebase structure.

[use-mcp:filesystem/read_directory:/src/]
[use-mcp:filesystem/read_file:/src/main.py]
```

**Listing available tools:**
```bash
./claude-loop.sh --list-mcp-tools

# Output:
Available MCP tools:
  filesystem/read_file - Read file contents
  filesystem/read_directory - Read directory listing
  filesystem/list_directory - List directory contents
  sqlite/query - Execute SQL query (read-only)
  sqlite/list_tables - List database tables
  sqlite/describe_table - Describe table schema
```

### Security Model

**Default: Read-Only**
- All MCP tools start read-only by default
- Write operations require explicit configuration
- Tools must be whitelisted to be used

**Whitelist Enforcement:**
```json
{
  "tools_whitelist": [
    "read_file",    // ✅ Allowed
    "write_file"    // ❌ Not in whitelist, will be blocked
  ]
}
```

**Schema Validation:**
- All tool calls validated against MCP schemas before execution
- Type checking on parameters
- Prevents malformed requests

### Migration Path

**Step 1: Start with read-only filesystem**
```json
{
  "servers": [{
    "name": "filesystem",
    "enabled": true,
    "tools_whitelist": ["read_file", "read_directory"],
    "config": {"readonly": true}
  }]
}
```

**Step 2: Add database access**
```json
{
  "servers": [
    { "name": "filesystem", "enabled": true },
    {
      "name": "sqlite",
      "enabled": true,
      "tools_whitelist": ["query", "list_tables"],
      "config": {"readonly": true}
    }
  ]
}
```

**Step 3: Gradually add more servers**
- Test each server individually
- Verify tool functionality before enabling in production
- Monitor logs for errors: `.claude-loop/logs/mcp.log`

### Troubleshooting

**Problem: MCP server connection fails**
```bash
# Check server is installed
npm list -g @modelcontextprotocol/server-filesystem

# Test connection manually
mcp-client connect @modelcontextprotocol/server-filesystem

# Check logs
tail -f .claude-loop/logs/mcp.log
```

**Problem: Tool not available**
```bash
# Verify tool is whitelisted
cat .claude-loop/mcp-config.json | jq '.servers[] | select(.name=="filesystem") | .tools_whitelist'

# List all available tools
./claude-loop.sh --list-mcp-tools
```

---

## Feature 2: Multi-Provider LLM (US-006)

### What is Multi-Provider?

Multi-provider support enables claude-loop to route tasks to the most cost-effective LLM based on task complexity. Simple tasks go to cheap models (Haiku, GPT-4o-mini), complex tasks to powerful models (Opus, O1).

**Expected Cost Reduction:** 30-50% on diverse workloads

### Enabling Multi-Provider

```bash
# Enable multi-provider feature
export ENABLE_MULTI_PROVIDER=true

# Or use command-line flag
./claude-loop.sh --enable-multi-provider --prd prd.json
```

### Configuration

Configuration is in `lib/llm_providers.yaml`:

```yaml
providers:
  # Anthropic (default)
  - name: claude-opus
    model: claude-opus-4-5-20250929
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075
    capabilities:
      - vision
      - tools
      - json_mode
    enabled: true

  - name: claude-sonnet
    model: claude-sonnet-4-5-20250929
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    capabilities:
      - vision
      - tools
      - json_mode
    enabled: true

  - name: claude-haiku
    model: claude-haiku-3-5-20241106
    cost_per_1k_input: 0.00025
    cost_per_1k_output: 0.00125
    capabilities:
      - vision
      - tools
    enabled: true

  # OpenAI
  - name: gpt-4o
    model: gpt-4o
    cost_per_1k_input: 0.0025
    cost_per_1k_output: 0.01
    capabilities:
      - vision
      - tools
      - json_mode
    enabled: false  # Enable if you have OpenAI API key

  - name: gpt-4o-mini
    model: gpt-4o-mini
    cost_per_1k_input: 0.00015
    cost_per_1k_output: 0.0006
    capabilities:
      - vision
      - tools
    enabled: false

  # Google
  - name: gemini-2.0-flash
    model: gemini-2.0-flash
    cost_per_1k_input: 0.0001
    cost_per_1k_output: 0.0004
    capabilities:
      - vision
      - tools
    enabled: false

  # DeepSeek (budget option)
  - name: deepseek-v3
    model: deepseek-chat
    cost_per_1k_input: 0.00014
    cost_per_1k_output: 0.00028
    capabilities:
      - tools
    enabled: false

routing:
  strategy: complexity_based
  thresholds:
    simple: 3      # complexity < 3 = cheap models
    complex: 7     # complexity >= 7 = powerful models
  fallback_chain:
    - claude-sonnet
    - claude-opus
    - gpt-4o
```

### Routing Logic

**Complexity-Based Routing:**
```python
if story.estimatedComplexity == "simple" or complexity_score < 3:
    providers = ["claude-haiku", "gpt-4o-mini", "gemini-2.0-flash"]
elif story.estimatedComplexity == "complex" or complexity_score >= 7:
    providers = ["claude-opus", "gpt-4o", "o1"]
else:  # medium
    providers = ["claude-sonnet", "gpt-4o", "deepseek-v3"]

# Filter by required capabilities
if story.requires_vision:
    providers = [p for p in providers if "vision" in p.capabilities]

# Select cheapest
selected = min(providers, key=lambda p: p.cost_per_1k_input)
```

### Cost Tracking

All provider usage is logged to `.claude-loop/logs/provider_usage.jsonl`:

```jsonl
{"timestamp":"2026-01-20T10:30:00Z","story_id":"US-001","iteration":1,"provider":"claude-haiku","model":"claude-haiku-3-5-20241106","input_tokens":5000,"output_tokens":1200,"cost_usd":0.0027,"complexity":2}

{"timestamp":"2026-01-20T10:35:00Z","story_id":"US-002","iteration":1,"provider":"claude-opus","model":"claude-opus-4-5-20250929","input_tokens":12000,"output_tokens":3500,"cost_usd":0.443,"complexity":8}
```

**View cost report:**
```bash
./claude-loop.sh --cost-report

# Output:
Cost Report (2026-01-20)
┌─────────────┬─────────┬───────────┬──────────┬──────────┐
│ Provider    │ Stories │ Tokens In │ Tokens Out│ Cost USD │
├─────────────┼─────────┼───────────┼──────────┼──────────┤
│ claude-haiku│   5     │   25,000  │   6,000  │   $0.014 │
│ claude-sonnet│  3     │   36,000  │  10,500  │   $0.266 │
│ claude-opus │   2     │   24,000  │   7,000  │   $0.885 │
├─────────────┼─────────┼───────────┼──────────┼──────────┤
│ Total       │  10     │   85,000  │  23,500  │   $1.165 │
└─────────────┴─────────┴───────────┴──────────┴──────────┘

Baseline (all opus): $2.378
Savings: $1.213 (51.0%)
```

### Per-Story Overrides

Override provider selection in PRD:

```json
{
  "id": "US-003",
  "title": "Critical security audit",
  "preferred_provider": "claude-opus",
  "required_capabilities": ["tools", "json_mode"]
}
```

### Fallback Chain

If primary provider fails (rate limit, error), the system tries secondary providers:

```
1. Try: claude-haiku (cheapest for simple task)
2. Fail: Rate limit exceeded
3. Fallback: claude-sonnet (next in chain)
4. Success: Task completed with claude-sonnet
```

### Migration Path

**Step 1: Enable for Phase 1 validation**
```bash
# Test with Claude providers only (no new API keys needed)
export ENABLE_MULTI_PROVIDER=true
# Haiku, Sonnet, Opus all use existing ANTHROPIC_API_KEY
./claude-loop.sh --prd prd.json
```

**Step 2: Add OpenAI (optional)**
```bash
export OPENAI_API_KEY="sk-..."
# Edit lib/llm_providers.yaml, set gpt-4o.enabled = true
./claude-loop.sh --prd prd.json
```

**Step 3: Monitor and optimize**
```bash
# Review cost savings
./claude-loop.sh --cost-report

# Adjust routing thresholds if needed
# Edit lib/llm_providers.yaml:
#   routing.thresholds.simple: 4  # Was 3, now more tasks use cheap models
```

### Troubleshooting

**Problem: Provider selection adds latency**
```bash
# Check selection overhead
tail -f .claude-loop/logs/provider_selection.log

# Should be <50ms per story
# If higher, check routing logic complexity
```

**Problem: Wrong provider selected**
```bash
# Check complexity score
cat .claude-loop/logs/provider_usage.jsonl | jq 'select(.story_id=="US-001") | .complexity'

# Override in PRD if needed
{
  "id": "US-001",
  "preferred_provider": "claude-opus"
}
```

---

## Feature 3: Bounded Delegation (US-007)

### What is Bounded Delegation?

Delegation enables hierarchical task decomposition for complex features. An agent can delegate subtasks to subordinate agents (max depth=2) with strict safety bounds.

**Use Cases:**
- Multi-component features (auth = JWT + UI + middleware)
- Layer-by-layer implementation (models → routes → middleware → tests)
- Parallel work on independent subsystems

### Enabling Delegation

```bash
# Enable delegation feature (experimental)
export ENABLE_DELEGATION=true

# Set limits (optional, defaults shown)
export MAX_DELEGATION_DEPTH=2           # Default: 2, max: 3
export MAX_CONTEXT_PER_AGENT=100000    # Default: 100k tokens
export MAX_DELEGATIONS_PER_STORY=10    # Default: 10

./claude-loop.sh --prd prd.json
```

### Safety Constraints

**Hard Limits:**
- `MAX_DELEGATION_DEPTH=2` (depth 0 → 1 → 2, cannot go to 3)
- `MAX_CONTEXT_PER_AGENT=100k` tokens
- `MAX_DELEGATIONS_PER_STORY=10` subtasks
- Cycle detection (A→B→A not allowed)
- Git worktree isolation (complete filesystem separation)

**Why Bounded?**
- Prevents runaway delegation chains
- Limits context explosion
- Ensures predictable costs
- Maintains execution safety

### Delegation Syntax

Claude uses this syntax in responses to delegate:

```markdown
I'll break this feature into 3 subtasks:

[delegate:Implement JWT token generation and validation:4]
[delegate:Create login UI component with form validation:3]
[delegate:Write integration tests for auth flow:2]

Each subtask will run in isolation and report results.
```

### Delegation Flow

```
1. Parent (US-007 at depth 0)
   ├── Detects [delegate:...] in Claude's response
   ├── Validates: depth < 2, no cycles, context OK
   └── Creates child US-007-DEL-001

2. Child Execution (US-007-DEL-001 at depth 1)
   ├── Creates git worktree: .claude-loop/workers/US-007-DEL-001
   ├── Sets DELEGATION_DEPTH=1
   ├── Executes via worker.sh
   ├── Can itself delegate to depth 2 (if needed)
   └── Returns results to parent

3. Result Integration
   ├── Summarizes child output (max 2k tokens)
   ├── Injects summary into parent context
   ├── Attributes child cost to parent
   └── Cleanup: removes worktree, archives logs
```

### Example: Two-Level Delegation

```
US-010: Implement e-commerce checkout (depth 0)
├── [delegate:Build shopping cart service:8] (depth 1)
│   ├── [delegate:Implement cart storage (Redis):3] (depth 2)
│   └── [delegate:Add cart item validation:2] (depth 2)
├── [delegate:Payment processing (Stripe):6] (depth 1)
└── [delegate:Order confirmation emails:3] (depth 1)
```

**Depth 2 is maximum:**
- US-010-DEL-001-DEL-001 (depth 2) cannot delegate further
- Attempting depth 3 → ERROR: "Delegation depth limit (2) reached"

### Cost Attribution

Child costs are attributed to parent story:

```
Story: US-010 (Checkout)
  Direct cost: $2.50
  Delegation costs:
    US-010-DEL-001 (Cart service): $0.80
      ├─ US-010-DEL-001-DEL-001 (Redis): $0.20
      └─ US-010-DEL-001-DEL-002 (Validation): $0.15
    US-010-DEL-002 (Payment): $0.65
    US-010-DEL-003 (Emails): $0.30
  Total cost: $4.60
```

### Delegation Logging

All delegations logged to `.claude-loop/logs/delegation.jsonl`:

```jsonl
{"timestamp":"2026-01-20T10:30:00Z","event":"delegation_created","parent":"US-010","child":"US-010-DEL-001","depth":1,"description":"Build shopping cart service","estimated_hours":8}

{"timestamp":"2026-01-20T10:45:00Z","event":"delegation_completed","child":"US-010-DEL-001","success":true,"duration_ms":900000,"cost_usd":0.80,"files_changed":["lib/cart.py","tests/test_cart.py"]}
```

**View delegation stats:**
```bash
./lib/delegation-tracker.sh stats

# Output:
{
  "total_delegations": 15,
  "max_depth_seen": 2,
  "active_delegations": 0,
  "max_allowed_depth": 2
}
```

### Migration Path

**Step 1: Test with simple delegation (depth 0 → 1)**
```bash
# Enable delegation
export ENABLE_DELEGATION=true

# Test with single-level delegation
# PRD should include estimatedComplexity: "complex" to trigger delegation
./claude-loop.sh --prd test-delegation.json
```

**Step 2: Monitor execution**
```bash
# Watch delegation log in real-time
tail -f .claude-loop/logs/delegation.jsonl

# Check for errors
grep "ERROR" .claude-loop/logs/delegation.jsonl
```

**Step 3: Verify results**
```bash
# Check delegation tree
cat .claude-loop/delegation/execution_graph.json | jq .

# Review child logs
ls -la .claude-loop/workers/*/logs/
```

**Step 4: Gradually increase complexity**
- Start with 1-2 delegations per story
- Then try two-level delegation (depth 0 → 1 → 2)
- Finally use for production features

### Troubleshooting

**Problem: "Delegation depth limit reached"**
```
ERROR: Delegation depth limit (2) reached. Cannot delegate further.
Current depth: 2
```

**Solution:** Implement task at current level without further delegation.

**Problem: "Context budget exceeded"**
```
ERROR: Agent context budget (100k tokens) exceeded.
Current context: 85,000 tokens
Subtask estimate: 35,000 tokens
Total: 120,000 tokens > 100,000 max
```

**Solutions:**
1. Summarize previous work to reduce parent context
2. Break subtask into smaller pieces
3. Increase MAX_CONTEXT_PER_AGENT (not recommended)

**Problem: "Delegation cycle detected"**
```
ERROR: Delegation cycle detected.
Cycle path: US-007 → US-007-DEL-001 → US-007 (attempted)
```

**Solution:** Review delegation logic. Subordinates cannot delegate back to ancestors.

---

## Combined Usage

### MCP + Multi-Provider

Use MCP tools with cost-optimized provider routing:

```bash
export ENABLE_MCP=true
export ENABLE_MULTI_PROVIDER=true

# Simple task: analyze files with MCP filesystem
# → Routes to claude-haiku (cheap)
# → Uses MCP tools for file access

./claude-loop.sh --prd analyze-codebase.json
```

### Multi-Provider + Delegation

Delegate to different providers based on subtask complexity:

```json
{
  "id": "US-040",
  "delegations": [
    {
      "description": "Simple validation logic",
      "preferred_provider": "claude-haiku"
    },
    {
      "description": "Complex algorithm design",
      "preferred_provider": "claude-opus"
    }
  ]
}
```

### All Features Enabled

```bash
export ENABLE_MCP=true
export ENABLE_MULTI_PROVIDER=true
export ENABLE_DELEGATION=true

./claude-loop.sh --prd complex-feature.json

# Results in:
# - Parent uses MCP filesystem tools
# - Delegates 3 subtasks
# - Subtask 1 → claude-haiku (simple)
# - Subtask 2 → claude-sonnet (medium)
# - Subtask 3 → claude-opus (complex)
```

---

## Rollback Strategy

All features are behind flags and can be disabled individually:

```bash
# Disable MCP only
export ENABLE_MCP=false

# Disable multi-provider (use default Claude)
export ENABLE_MULTI_PROVIDER=false

# Disable delegation
export ENABLE_DELEGATION=false

# Disable all Phase 2 features (complete rollback)
unset ENABLE_MCP ENABLE_MULTI_PROVIDER ENABLE_DELEGATION
./claude-loop.sh --prd prd.json  # Pure Phase 1 execution
```

### Git Rollback

If Phase 2 introduces issues:

```bash
# Stash current work
git stash

# Return to Phase 1
git checkout main  # Or your pre-Phase-2 branch

# Verify Phase 1 still works
./claude-loop.sh --prd test-prd.json
```

---

## Performance Impact

### Overhead Measurements

| Feature | Overhead | Measurement |
|---------|----------|-------------|
| MCP | ~50ms per tool call | Includes JSON-RPC round-trip |
| Multi-Provider | <1ms per selection | In-memory provider lookup |
| Delegation | ~200ms per delegation | Includes worktree creation |

**Total overhead:** <5% in typical usage

### Cost Savings

| Scenario | Phase 1 Cost | Phase 2 Cost | Savings |
|----------|--------------|--------------|---------|
| All simple tasks | $5.00 (all opus) | $0.35 (all haiku) | 93% |
| Mixed workload | $10.00 | $4.50 | 55% |
| All complex tasks | $15.00 | $14.50 (mostly opus) | 3% |

**Average savings:** 30-50% on diverse workloads

---

## Validation and Testing

### Integration Tests

Run Phase 2 integration tests:

```bash
# Full test suite
make test-phase2

# Individual feature tests
make test-mcp
make test-multi-provider
make test-delegation

# Combined features
make test-integration
```

### Validation Checklist

Before deploying Phase 2 to production:

- [ ] All integration tests passing (>90% coverage)
- [ ] MCP servers configured and tested
- [ ] API keys for desired providers configured
- [ ] Cost tracking verified (provider_usage.jsonl accurate)
- [ ] Delegation depth limits enforced
- [ ] Cycle detection working
- [ ] Rollback tested (all features can be disabled)
- [ ] Documentation reviewed
- [ ] Team trained on new features

---

## Next Steps

1. **US-010 Validation:** Run real-world tasks and measure improvements
2. **Incremental Rollout:** Enable features one at a time
3. **Monitor Metrics:** Track cost savings, success rates, execution time
4. **Iterate:** Adjust thresholds based on actual usage

## Support

- Documentation: `docs/features/` (mcp-integration.md, multi-provider-llm.md, bounded-delegation.md)
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Issues: GitHub Issues on claude-loop repository
- PRD: `prds/phase2-tier2-library-integration.json`
