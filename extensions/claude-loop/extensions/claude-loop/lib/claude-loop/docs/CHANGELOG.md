# Changelog

All notable changes to claude-loop will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - Phase 2 Tier 2: Library Integration - 2026-01-20

### Added

**MCP (Model Context Protocol) Integration (US-005)**
- MCP client with Python asyncio for JSON-RPC communication
- Server discovery and tool enumeration
- MCP bridge layer (bash functions) for claude-loop integration
- Security features:
  - Whitelist-only tool execution
  - Read-only default for filesystem and database tools
  - Schema validation for all tool parameters
  - Audit logging to `.claude-loop/logs/mcp_calls.jsonl`
- Example server configurations: filesystem (read-only), sqlite (read-only)
- CLI flags: `--enable-mcp`, `--list-mcp-tools`
- Configuration: `.claude-loop/mcp-config.json` for server endpoints and whitelists
- Documentation: `docs/features/mcp-integration.md` (1823 lines)
- Integration tests: `tests/mcp_test.sh` (13 tests)

**Multi-Provider LLM Support (US-006)**
- LiteLLM integration for 100+ LLM providers
- Complexity-based provider selection:
  - Simple tasks (complexity < 3) → Haiku/GPT-4o-mini
  - Medium tasks (complexity 3-5) → Sonnet/GPT-4o
  - Complex tasks (complexity > 5) → Opus/O1
- Supported providers:
  - Anthropic (Claude Haiku, Sonnet, Opus)
  - OpenAI (GPT-4o, GPT-4o-mini, O1)
  - Google (Gemini 2.0)
  - DeepSeek (V3, R1)
- Cost tracking and reporting:
  - Per-iteration logging to `.claude-loop/logs/provider_usage.jsonl`
  - Cost report: `./claude-loop.sh --cost-report`
  - Expected savings: 30-50% on mixed workloads, 70%+ on simple tasks
- Fallback chain: primary → secondary → Claude CLI (always available)
- CLI flags: `--enable-multi-provider`, `--cost-report`
- Configuration: `lib/llm_providers.yaml` for provider costs and capabilities
- Documentation: `docs/features/multi-provider-llm.md` (1638 lines)
- Integration tests: `tests/multi_provider_test.sh` (15 tests)

**Bounded Delegation (US-007)**
- Hierarchical task delegation with strict limits:
  - MAX_DELEGATION_DEPTH=2 (parent → child → grandchild, no further)
  - MAX_CONTEXT_PER_AGENT=100k tokens
  - Cycle detection (DAG-only delegation graph)
- Delegation syntax: `[delegate:description:estimated_hours]`
- Git worktree isolation for each subtask
- Parallel execution capability for delegated subtasks
- Cost attribution (child costs → parent story)
- Delegation tracking and visualization:
  - Hierarchy logging to `.claude-loop/logs/delegation.jsonl`
  - Visualization: `python3 lib/delegation_visualizer.py show`
- CLI flag: `--enable-delegation` (experimental)
- Documentation: `docs/features/bounded-delegation.md` (1280 lines)
- Integration tests: `tests/delegation_test.sh` (35+ tests)

**Comprehensive Integration Testing (US-008)**
- Phase 2 integration test suite: `tests/phase2_integration_test.sh` (20+ tests)
- Test categories:
  - Individual feature tests (MCP, Multi-Provider, Delegation)
  - Combined feature tests (MCP+Multi, Delegation+Multi, All features)
  - Performance tests (<5% overhead validation)
  - Rollback tests (feature flag disable, Phase 1 fallback)
  - Error injection tests (server crash, API failure, context overflow)
- Makefile automation: `make test-phase2`
- Total test coverage: 83+ tests (63+ individual + 20+ integration)
- Documentation: `tests/README.md` updated with Phase 2 testing guide

**Documentation and Migration Guide (US-009)**
- Comprehensive migration guide: `docs/MIGRATION_TIER2.md` (821 lines)
  - Prerequisites and dependencies
  - Feature-by-feature migration paths
  - Configuration examples
  - Troubleshooting guide
  - Rollback strategy
- Example configurations:
  - `.claude-loop/mcp-config.example.json` (5 server examples)
  - `lib/llm_providers.example.yaml` (10 providers)
- Example PRDs:
  - `prds/examples/mcp-usage-example.json` (4-story codebase analysis workflow)
  - `prds/examples/delegation-example.json` (delegation workflow)
- Updated architecture documentation:
  - `docs/architecture/architecture.md` - Complete Phase 2 architecture with diagrams
  - `docs/TROUBLESHOOTING.md` - Phase 2 Tier 2 integration issues section
- Updated CHANGELOG.md (this file)

### Changed

- Provider selection now routes to cheapest capable provider (not always Opus)
- Execution logs now include provider used, MCP calls, and delegation hierarchy
- Cost reports now show Phase 1 vs Phase 2 savings comparison
- Worker execution enhanced to support delegation with git worktrees

### Fixed

- Provider fallback chain now properly handles rate limits
- MCP tool execution now has 5-second timeout protection
- Delegation cycle detection now prevents A→B→A loops
- Context size validation prevents delegation overflow

### Security

- MCP tools default to read-only mode
- API keys stored only in environment variables (never in config files)
- Delegation depth and context limits strictly enforced
- Audit logging for all MCP calls and delegations

### Performance

- Provider selection overhead: <1ms (target: <50ms)
- MCP local tool call latency: 200-400ms (target: <500ms)
- Delegation creation overhead: +10-16% (beneficial for 3+ parallel subtasks)
- Cost savings: 65% on typical mixed workloads vs Phase 1 Opus-only

### Breaking Changes

None. All Phase 2 Tier 2 features are behind feature flags (disabled by default):
- `ENABLE_MCP=false` (default)
- `ENABLE_MULTI_PROVIDER=false` (default)
- `ENABLE_DELEGATION=false` (default, experimental)

Phase 1 workflows remain unchanged and fully supported.

---

## [2.1.0] - Phase 2 Tier 1: Skills & Daemon - 2026-01-13

### Added

**Skills Architecture (US-201, US-202)**
- Progressive disclosure framework: metadata → instructions → resources
- On-demand loading (<100 tokens per skill at startup)
- Skill execution engine (bash/python script support)
- CLI flags: `--list-skills`, `--skill <name>`, `--skill-arg <value>`
- 6 priority skills implemented:
  - `hello-world` - Example skill template
  - `prd-validator` - Validate PRD structure and dependencies
  - `test-scaffolder` - Generate test file scaffolding
  - `commit-formatter` - Enforce Conventional Commits standard
  - `api-spec-generator` - Generate OpenAPI specs from code
  - `cost-optimizer` - Analyze complexity and recommend models
- Documentation: `docs/features/skills-architecture.md`
- Skills directory structure: `skills/<skill-name>/SKILL.md`

**Quick Task Mode (US-203, US-204)**
- No-PRD execution for fast tasks
- Natural language task description input
- Automatic plan generation with user approval
- Auto-commit on success
- Advanced features:
  - Complexity detection (0-100 score)
  - Auto-escalation to PRD mode (threshold: 60)
  - Task chaining (sequential execution)
  - 3 templates: refactor, add-tests, fix-bug
  - Dry-run mode: `--dry-run` (preview plan without executing)
  - Resume failed tasks: `--continue`
  - Cost estimation before execution
  - Progress checkpointing (every 5 steps)
  - Concurrent execution with workspace isolation
  - History tracking: `./claude-loop.sh quick history`
- CLI: `./claude-loop.sh quick "task description"`
- Documentation: `docs/features/quick-task-mode.md`

**Daemon Mode (US-205, US-206)**
- Background task execution
- Task queue management (FIFO with priority)
- Worker pool (configurable, default: 1 worker)
- PID-based process management
- Graceful shutdown (finish current task before stopping)
- Priority queuing: high/normal/low
- Notification system:
  - Email (sendmail/SMTP)
  - Slack webhook
  - Generic webhook (POST JSON)
  - Retry logic with exponential backoff
  - 3 templates: success, failure, checkpoint
- CLI: `./claude-loop.sh daemon {start|stop|status|submit|queue}`
- Configuration: `.claude-loop/daemon/notifications.json`
- Documentation: `docs/features/daemon-mode.md`, `docs/features/daemon-notifications.md`

**Visual Progress Dashboard (US-207, US-208)**
- Flask REST API backend with Server-Sent Events (SSE)
- Real-time web UI:
  - Live execution view (current story, progress %, elapsed time)
  - Color-coded story status grid (green/yellow/gray with pulsing)
  - Streaming logs viewer
  - Cost tracker with budget alerts
  - File changes diff viewer
  - Historical runs view
  - Dark mode toggle
  - Settings panel (refresh rate, budget limit, notifications)
- Responsive design (mobile/tablet/desktop)
- Token-based authentication (auto-generated Bearer tokens)
- API endpoints:
  - `/api/status`, `/api/stories`, `/api/logs`, `/api/metrics`
  - `/api/stream` (SSE for real-time updates)
  - `/api/history`
- CLI: `./claude-loop.sh dashboard {start|stop|restart|status|logs}`
- Access: http://localhost:8080
- Documentation: `docs/api/dashboard-api.md`, `docs/features/dashboard-ui.md`

**Integration and Testing (US-209)**
- Skills framework integrated with quick task mode
- Daemon integrated with dashboard (queue visibility)
- Notifications integrated with dashboard
- Integration test workflow: quick task → daemon submission → dashboard monitoring → notification
- 13 integration tests (all passing)
- Phase 1 regression testing (all features still working)
- Performance benchmarks (no regression detected)

**Documentation and Onboarding (US-210)**
- Getting started guide: `docs/phase2/getting-started.md`
- Skills development tutorial: `docs/phase2/skills-development.md`
- Quick task mode tutorial: `docs/phase2/quick-task-mode.md`
- Daemon mode tutorial: `docs/phase2/daemon-mode.md`
- Dashboard tutorial: `docs/phase2/dashboard.md`
- Troubleshooting guide: `docs/phase2/phase2-troubleshooting.md`
- CLI reference: `docs/phase2/cli-reference.md`
- FAQ: `docs/phase2/FAQ.md`
- Before/after comparison: `docs/phase2/before-after-comparison.md`
- Announcement blog post draft: `docs/phase2/announcement-blog-post.md`
- Video storyboard: `docs/phase2/video-storyboard.md`
- Migration guide: `docs/MIGRATION-PHASE2.md`

### Changed

- Agent loading now uses progressive disclosure (skills framework)
- Task execution can now bypass PRD authoring (quick mode)
- Execution can now run in background (daemon mode)
- Progress now visible in real-time web UI (dashboard)

### Performance

- Skills metadata loading: <100 tokens per skill (95% reduction vs manual prompts)
- Quick mode execution: 2-5 minutes for simple tasks
- Daemon throughput: 3x-5x improvement with 3-5 parallel PRDs
- Dashboard SSE latency: <100ms for status updates

---

## [1.0.0] - Phase 1: Foundations - 2026-01-07

### Added

**Core Features**
- PRD-based task state machine (`prd.json`)
- Story-by-story execution loop
- Persistent memory:
  - `progress.txt` - Append-only learnings log
  - `AGENTS.md` - Pattern documentation
  - `.claude-loop/sessions/` - Session state and checkpoints
- Agent system:
  - Semantic matching (story description → agent expertise)
  - Keyword matching (story keywords → agent triggers)
  - Bundled agents: code-reviewer, test-runner, debugger, security-auditor, git-workflow
- Experience store:
  - ChromaDB vector storage
  - Domain-aware RAG (web, unity, ml, physical)
  - Problem-solution retrieval with feedback tracking
- Quality gates:
  - Tests (pytest/jest/cargo test)
  - Typecheck (mypy/tsc/cargo check)
  - Linter (pylint/eslint/clippy)
- Git workflow:
  - Atomic commits per story
  - Descriptive messages with AC met
  - Branch management
- Monitoring and cost tracking:
  - Per-iteration metrics logging
  - HTML report generation
  - Cost breakdown by story
- Parallel execution:
  - Git worktree isolation
  - Dependency graph execution
  - File conflict detection
  - Model selector (complexity-based: Haiku/Sonnet/Opus)

**Configuration**
- `config.yaml` for quality gates
- Environment variables for API keys
- PRD schema validation
- Dependency cycle detection

**Documentation**
- README.md with architecture overview
- AGENTS.md with discovered patterns
- Agent prompts in `agents/` directory
- Performance and security audits

### Performance

- PRD validation: ~200ms (optimized with batched jq calls)
- Story selection: ~50ms
- Parallel execution: 3x-5x throughput improvement
- Context caching for unchanged files

### Security

- Path traversal protection (symlink resolution)
- Command injection prevention (shell=False, whitelist)
- File locking for concurrent access
- Sandbox validation for file access

---

## [0.9.0] - Multi-LLM Support - 2025-12-15

### Added

- Multi-LLM provider abstraction
- Code review panel (multiple LLMs review in parallel)
- Vision analyzer for screenshots
- Reasoning router (route complex problems to O1/R1)
- Cost tracker across providers

### Supported Providers

- Claude (Anthropic API)
- GPT-4o (OpenAI)
- Gemini 2.0 (Google)
- DeepSeek V3 and R1

---

## [0.5.0] - Initial Release - 2025-11-01

### Added

- Basic PRD parsing
- Story execution loop
- Claude API integration
- Git commit automation
- Progress logging

---

## Release Comparison Table

| Feature | Phase 1 (1.0.0) | Phase 2.1 (2.1.0) | Phase 2.2 (2.2.0) |
|---------|-----------------|-------------------|-------------------|
| PRD-based execution | ✓ | ✓ | ✓ |
| Skills framework | - | ✓ | ✓ |
| Quick task mode | - | ✓ | ✓ |
| Daemon mode | - | ✓ | ✓ |
| Visual dashboard | - | ✓ | ✓ |
| MCP integration | - | - | ✓ |
| Multi-provider LLM | - | - | ✓ |
| Bounded delegation | - | - | ✓ |
| Cost savings | 0% (baseline) | ~5-10% | 30-50% |
| Parallel execution | ✓ | ✓ | ✓ |
| Experience store | ✓ | ✓ | ✓ |

---

## Upgrade Paths

**Phase 1 → Phase 2.1**: See `docs/MIGRATION-PHASE2.md`
**Phase 2.1 → Phase 2.2**: See `docs/MIGRATION_TIER2.md`

---

## Versioning Strategy

- **Major version** (X.0.0): Breaking changes, architecture overhaul
- **Minor version** (0.X.0): New features, backward compatible
- **Patch version** (0.0.X): Bug fixes, documentation updates

Current version follows semantic versioning with phases:
- 1.x.x = Phase 1 (Foundations)
- 2.1.x = Phase 2 Tier 1 (Skills & Daemon)
- 2.2.x = Phase 2 Tier 2 (Library Integration)

---

*For detailed feature documentation, see `docs/features/` directory.*
*For migration guides, see `docs/MIGRATION-*.md` files.*
*For troubleshooting, see `docs/TROUBLESHOOTING.md`.*
