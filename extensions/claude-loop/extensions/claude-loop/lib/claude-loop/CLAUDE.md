# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**claude-loop** is an autonomous coding agent that implements entire features by breaking them into story-sized chunks that fit within Claude's context window. It uses persistent file-based memory (PRDs, progress logs, agent patterns) and a domain-aware experience store (vector database) to maintain context across iterations and learn from past implementations.

## Common Development Commands

### Basic Execution

```bash
# Single-command entry point (auto-generates PRD)
./claude-loop.sh "Add user authentication with OAuth"

# Traditional PRD-based execution
./claude-loop.sh --prd prd.json

# Resume from checkpoint
./claude-loop.sh --resume

# Run with specific PRD
./claude-loop.sh --prd prds/active/my-feature/prd.json
```

### Parallel Execution

```bash
# Execute multiple PRDs simultaneously (max 3 by default)
./claude-loop.sh --parallel

# Configure max parallel PRDs
./claude-loop.sh --parallel --max-prds 5

# Monitor all running PRDs
./claude-loop.sh --status

# Stop specific PRD
./claude-loop.sh --stop PRD-001
```

### Quick Task Mode (Phase 2)

```bash
# Execute without PRD authoring
./claude-loop.sh quick "add tests to the login module"

# Dry-run mode (show plan without executing)
./claude-loop.sh quick "refactor error handling" --dry-run

# Use templates
./claude-loop.sh quick --template refactor "clean up utils"
```

### Daemon Mode (Phase 2)

```bash
# Start background daemon
./claude-loop.sh daemon start

# Submit tasks to queue
./claude-loop.sh daemon submit prd.json --priority high --notify email

# Monitor queue
./claude-loop.sh daemon status
./claude-loop.sh daemon queue

# Stop daemon
./claude-loop.sh daemon stop
```

### Dashboard (Phase 2)

```bash
# Start real-time web dashboard
./claude-loop.sh dashboard start
# Open http://localhost:8080

# Dashboard features:
# - Live execution view
# - Story status grid
# - Streaming logs
# - Cost tracker
# - Historical runs
```

### Skills System (Phase 2)

```bash
# List available skills
./claude-loop.sh --list-skills

# Use specific skill
./claude-loop.sh --skill prd-validator --skill-arg prd.json
./claude-loop.sh --skill test-scaffolder --skill-arg src/auth.py

# Built-in skills:
# - prd-validator: Validate PRD format
# - test-scaffolder: Generate test boilerplate
# - commit-formatter: Format commit messages
# - api-spec-generator: Generate OpenAPI specs
# - cost-optimizer: Analyze and optimize token usage
```

### PRD Management

```bash
# Generate PRD from description (Phase 3)
./claude-loop.sh --dynamic "Implement JWT authentication with login, signup, and password reset"

# With codebase analysis for file scopes
./claude-loop.sh --dynamic "Add comment system to blog" --codebase-analysis

# List PRD templates
./claude-loop.sh --list-templates

# Generate from template
./claude-loop.sh --template web-feature --template-var FEATURE_NAME=user-auth

# List PRDs by status
python lib/prd-manager.py list --status active
python lib/prd-manager.py list --status completed

# Search PRDs
python lib/prd-indexer.py search "authentication"
```

### Experience Store

```bash
# Search for similar problems
python lib/experience-store.py search "JWT refresh token not working" --domain web

# Record a solution
python lib/experience-store.py store "problem" "solution" --domain unity:xr

# View domain statistics
python lib/experience-store.py stats --by-domain

# Provide feedback on retrieval quality
python lib/experience-store.py feedback <experience_id> --helpful
```

### Testing

```bash
# Run test suite
pytest tests/ -v

# Run specific test file
pytest tests/test_failure_classification.py -v

# Run with output (see metrics)
pytest tests/test_failure_classification.py -v -s

# Run classification accuracy validation
pytest tests/test_failure_classification.py::test_classification_accuracy -v -s

# Current test coverage:
# - Classification accuracy: 95.83% (>80% required for autonomous mode)
# - 24 manually labeled test cases across 4 failure categories
```

### Development Workflow

```bash
# Verify core file protection
python lib/core-protection.py check claude-loop.sh

# Check calibration metrics
python lib/calibration-tracker.py report

# Monitor health indicators
python lib/health-indicators.py report

# Detect conflicts in improvement proposals
python lib/conflict-detector.py check
```

## High-Level Architecture

### Core Loop Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              claude-loop Execution Flow                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Read State                                              │
│     ├── prd.json (tasks)                                    │
│     ├── progress.txt (learnings)                            │
│     └── AGENTS.md (patterns)                                │
│                                                              │
│  2. Retrieve Experience (domain-aware RAG)                  │
│     └── ChromaDB vector store                               │
│                                                              │
│  3. Select Story (highest priority incomplete)              │
│                                                              │
│  4. Select Agents (semantic + keyword matching)             │
│     ├── Tier 1: Core agents (always trusted)               │
│     └── Tier 2: Curated specialists                         │
│                                                              │
│  5. Implement Story (with quality gates)                    │
│     ├── Tests must pass                                     │
│     ├── Types must check                                    │
│     └── Linter must pass                                    │
│                                                              │
│  6. Commit (atomic with descriptive message)                │
│                                                              │
│  7. Record Experience (problem-solution with domain)        │
│                                                              │
│  8. Repeat until all stories pass                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Stratified Memory Architecture (v2)

The system maintains 4 layers of memory to enable learning without bloat:

**L0: Immutable Core**
- `claude-loop.sh`, `lib/*.sh`, `lib/core-protection.py`
- NEVER modified by automation
- Changes require manual human commits with issue approval

**L1: Domain Adapters**
- `agents/*.md`, `adapters/*/`
- Promoted after 100+ successes + human review
- Provide specialized knowledge for tech stacks (Physical AI, Unity XR, etc.)

**L2: Experience Store (RAG)**
- ChromaDB with domain-partitioned collections
- Domain-aware storage: `web/*`, `unity/*`, `physical/*`, `ml/*`
- Retrieval with feedback tracking (helpful_rate)
- Per-domain LRU eviction when DB exceeds 500MB
- Located in `~/.claude-loop/experience-store/`

**L3: Improvement Queue**
- Human-gated proposals awaiting promotion
- Conflict detection before promotion
- Calibration tracking (95% alignment required over 6 months)

### Parallel Execution Architecture

**Git Worktree Isolation**: Each PRD runs in its own worktree on a dedicated branch
- Complete isolation, no conflicts between parallel executions
- Atomic operations with file-based locking
- Resource management with API rate limiting and max PRD enforcement
- 3x-5x throughput improvement

**Worker Model**:
- Coordinator process manages PRD queue
- Worker processes execute PRDs in separate worktrees
- Status tracking via `.claude-loop/workers/*/status.json`
- Graceful shutdown with checkpoint support

### Adaptive Story Splitting (Phase 3)

Real-time complexity detection that automatically breaks down stories:

**4 Complexity Signals** (weighted):
- Time overrun (35%): AC took 3.2x estimated time
- File expansion (25%): 4 files modified outside initial scope
- Error count (25%): 5 errors encountered
- Clarifications (15%): Agent requested clarification 2 times

**Threshold**: Default 7/10, configurable via `--complexity-threshold`

**Process**:
1. Monitor signals during execution
2. Calculate complexity score (0-10)
3. When score exceeds threshold, Claude generates 2-4 sub-stories
4. Interactive approval: [a]pprove, [r]eject, [e]dit, [s]kip
5. PRD updates atomically, execution continues with first sub-story
6. Full audit trail in `complexity-signals.jsonl` and `split-proposals.jsonl`

### Skills Architecture (Phase 2)

Deterministic operations with progressive disclosure (50 tokens/skill vs 200-500):

**Skill Structure**:
```
skills/
├── prd-validator/
│   ├── skill.yaml          # Metadata and interface
│   ├── handler.sh          # Implementation
│   └── examples/           # Usage examples
└── test-scaffolder/
    ├── skill.yaml
    └── handler.py
```

**Skill Interface**:
- Standard input/output format
- Token efficiency (<50 tokens to invoke)
- Composable (skills can call other skills)
- Version controlled with semantic versioning

### Multi-LLM Support

Flexible provider abstraction for different use cases:

**Providers**:
- Claude (default): Complex coding, tool use (primary)
- GPT-4o: General, vision analysis
- Gemini 2.0: Fast, vision, long context (2M tokens)
- DeepSeek V3: Coding, math (budget-friendly)
- DeepSeek R1: Deep reasoning

**Usage**:
```bash
# Multi-LLM code review
./claude-loop.sh --enable-review --reviewers openai,gemini,deepseek

# Vision analysis
python lib/vision_analyzer.py analyze camera.png --mode safety_check

# Use different provider as primary
./claude-loop.sh --provider gemini "Add user authentication"
```

**Modules**: `lib/llm_provider.py`, `lib/review_panel.py`, `lib/vision_analyzer.py`, `lib/cost_tracker.py`

## Key Implementation Details

### PRD Format

PRDs are JSON files with this structure:

```json
{
  "project": "feature-name",
  "branchName": "feature/feature-name",
  "description": "Brief feature description",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a <role>, I want <goal> so that <benefit>",
      "acceptanceCriteria": [
        "Testable criterion 1",
        "Testable criterion 2"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

**Key Fields**:
- `priority`: Lower number = higher priority (story selection order)
- `passes`: `false` = incomplete, `true` = complete and validated
- `acceptanceCriteria`: Must be testable and verifiable
- `fileScope` (optional): Limit changes to specific files
- `dependencies` (optional): Story IDs that must complete first
- `estimatedComplexity` (optional): simple/medium/complex
- `suggestedModel` (optional): haiku/sonnet/opus

### PRD Lifecycle

PRDs move through states in `prds/` directory:

```
drafts/ → active/ → completed/
                 ↘ abandoned/
```

Each PRD directory contains:
- `MANIFEST.yaml`: Metadata, status, approval info
- `prd.json`: User stories with acceptance criteria
- `progress.txt`: Implementation notes (append-only log)

**Lifecycle Commands**:
```bash
python lib/prd-manager.py promote PRD-001        # drafts → active
python lib/prd-manager.py complete PRD-001       # active → completed
python lib/prd-manager.py abandon PRD-001        # active → abandoned
```

### Agent System

Agents provide specialized expertise through markdown prompt files:

**Bundled Agents** (Tier 1):
- `code-reviewer`: Quality & security reviews
- `test-runner`: Test execution and coverage
- `debugger`: Systematic debugging
- `security-auditor`: OWASP scanning
- `git-workflow`: Safe git operations

**Agent Selection**:
- Semantic matching: Story description → agent expertise
- Keyword matching: Story keywords → agent triggers
- Priority ranking: Relevance score + tier weighting
- Max agents per iteration: 2 (configurable)

**Agent Registration**:
```bash
# Semantic + keyword matching
python lib/agent-registry.sh match "implement OAuth authentication"

# List available agents
python lib/agent-registry.sh list --tier 1
```

### Core File Protection

Foundational files are protected from automation:

**Immutable Core** (cannot be unprotected):
- `claude-loop.sh`
- `lib/core-protection.py`
- `lib/execution-logger.sh`

**Protected Core** (can be unprotected if necessary):
- `lib/prd-parser.sh`, `lib/monitoring.sh`, `lib/worker.sh`, `lib/parallel.sh`
- `lib/merge-controller.py`, `prompt.md`, `AGENTS.md`

**Modification Process**:
1. Create GitHub issue with impact analysis
2. Discussion and approval from maintainers
3. Manual implementation (automation will refuse)
4. Full test suite validation
5. Commit with issue reference

### Session State & Checkpoints

Sessions auto-save progress for resumability:

**Session Files**:
- `.claude-loop/sessions/<id>/state.json`: Full session state
- `.claude-loop/sessions/<id>/checkpoint.json`: Latest checkpoint
- `.claude-loop/sessions/last-session-id`: Points to most recent session

**Resume Options**:
```bash
./claude-loop.sh --resume                    # Resume last session
./claude-loop.sh --resume-from <id>          # Resume specific session
./claude-loop.sh --list-sessions             # List available sessions
```

### Quality Gates

Before marking a story complete, validation runs:

1. **Syntax**: Language parsers validate compilation
2. **Type Checking**: Type systems verify correctness
3. **Linting**: Code style and quality checks
4. **Security**: OWASP scanning for vulnerabilities
5. **Tests**: Unit tests (≥80%) and integration tests (≥70%)
6. **Performance**: Benchmarking and optimization check
7. **Documentation**: Completeness and accuracy validation
8. **Integration**: E2E testing and deployment validation

**Configuration**: Via `config.yaml`:
```yaml
quality:
  require_tests: true
  require_typecheck: true
  require_lint: false
  min_coverage: 0
  security_scan: false
```

### Privacy & Local-First Design

**Default Mode**: `FULLY_LOCAL`
- All code stays local (only goes to Anthropic API)
- Experience stored in `~/.claude-loop/`
- Zero telemetry by default
- No data sent to third parties

**Team Sharing** (optional):
```bash
# Export experiences for team sync
python lib/experience-store.py export --domain web --output team-web.json

# Import team experiences
python lib/experience-store.py import team-web.json
```

## Module Organization

The codebase uses a lib/ directory for ~53 Python modules and ~21 shell scripts:

**Core Modules**:
- `experience-store.py`: Domain-aware vector storage (ChromaDB)
- `domain-detector.py`: Automatic project domain detection
- `calibration-tracker.py`: Track human alignment over time
- `conflict-detector.py`: Detect contradictory improvements
- `health-indicators.py`: Leading indicator metrics

**Invisible Intelligence** (Phase 1):
- `complexity-detector.py`: Auto-detect complexity (0-4)
- `progress-dashboard.py`: Real-time visual progress
- `quality-gates.py`: Automatic validation pipeline
- `session-state.py`: Checkpoint and resume support

**Multi-LLM** (Phase 0.9):
- `llm_provider.py`: Provider abstraction
- `review_panel.py`: Multi-LLM code review
- `vision_analyzer.py`: Vision analysis routing
- `reasoning_router.py`: Route to reasoning models
- `cost_tracker.py`: Track costs across providers

**Phase 2 Foundations**:
- `daemon.sh`: Background task execution
- `dashboard/`: Real-time web UI (Flask + SSE)
- `skills/*/`: Deterministic operation modules
- `notifications.py`: Multi-channel notifications

**Phase 3 Features**:
- `complexity-monitor.sh`: Real-time complexity tracking
- `story-splitter.py`: Adaptive story decomposition
- `dynamic-prd-generator.py`: PRD generation from descriptions

## Development Patterns

### Adding New Skills

1. Create skill directory: `skills/my-skill/`
2. Add `skill.yaml` with metadata and interface
3. Implement `handler.sh` or `handler.py`
4. Add examples in `examples/`
5. Register with `./claude-loop.sh --list-skills`

### Adding Domain Adapters

1. Copy example: `cp -r adapters/example adapters/my-domain`
2. Customize prompts in `prompts/`
3. Add tools in `tools/` (JSON configs)
4. Implement validators in `validators/` (Python)
5. Test with `--agents-dir adapters/my-domain`

### Contributing Core Changes

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines:
- Core file changes require issue approval
- All changes must pass full test suite
- Manual commits only (no automation)
- Impact analysis required

### Testing Requirements

- Classification accuracy must remain >80% for autonomous mode
- New features require tests with >70% coverage
- Core module changes require regression tests
- Use `pytest tests/ -v` to run full suite

## Performance Characteristics

**Throughput**:
- Single PRD: 5-10 stories in 30-60 minutes
- Parallel mode: 3x-5x improvement with 3-5 PRDs
- Quick mode: Simple tasks in 2-5 minutes

**Token Usage**:
- Typical feature: 50K-150K tokens ($1-5)
- Skills: 50 tokens vs 200-500 for manual prompts (95% reduction)
- Experience augmentation: +2K-5K tokens per retrieval

**Scalability**:
- Experience store: 500MB per domain (auto-LRU eviction)
- Parallel PRDs: 3-5 concurrent (configurable)
- Domain partitioning: Scales to 1000+ users without bloat

## Troubleshooting

**Issue**: Story marked complete but tests still fail
- Check quality gate configuration in `config.yaml`
- Review `progress.txt` for validation errors
- Run tests manually: `pytest tests/ -v`

**Issue**: Agent not being selected
- Check agent triggers in agent manifest
- Verify tier is enabled: `--agent-tiers 1,2`
- Use `python lib/agent-registry.sh match "your query"` to debug

**Issue**: Experience retrieval not helpful
- Provide feedback: `python lib/experience-store.py feedback <id> --not-helpful`
- Check domain matching: experiences need same domain context
- Review domain detection: `python lib/domain-detector.py detect`

**Issue**: Parallel execution conflicts
- Each PRD runs in isolated worktree (no conflicts possible)
- Check worker status: `./claude-loop.sh --status`
- Review worker logs: `.claude-loop/workers/*/logs/`

**Issue**: High token costs
- Use cost optimizer skill: `./claude-loop.sh --skill cost-optimizer`
- Review experience retrieval (reduce if too verbose)
- Consider haiku for simple stories: set `suggestedModel: "haiku"`
- Enable quick mode for simple tasks

For more details, see the comprehensive documentation in `docs/` and the architecture decision records in `docs/adrs/`.
