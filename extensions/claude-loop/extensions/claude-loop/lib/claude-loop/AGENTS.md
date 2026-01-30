# AGENTS.md - Pattern Documentation

This file documents patterns discovered during development for AI agents
and future developers. Updated automatically by claude-loop iterations.

## Project Structure

```
claude-loop/
├── claude-loop.sh       # Main script - orchestrates iterations
├── prompt.md            # Iteration prompt template
├── prd.json             # Task state machine (user stories)
├── progress.txt         # Append-only learnings log
├── .gitignore           # Excludes runtime data from version control
├── lib/
│   ├── agent-registry.sh    # Agent selection and loading
│   ├── semantic-matcher.py  # Semantic matching for agents
│   ├── monitoring.sh        # Cost and metrics tracking + JSON logging
│   ├── report-generator.py  # HTML report generation
│   ├── agent-improver.py    # Agent improvement suggestion analysis
│   ├── prd-parser.sh        # PRD schema validation + parallelization support
│   ├── dependency-graph.py  # Build dependency graph and execution plan
│   ├── model-selector.py    # Intelligent model selection for cost optimization
│   ├── worker.sh            # Single-story worker for parallel execution
│   ├── parallel.sh          # Parallel group executor for concurrent story execution
│   ├── merge-controller.py  # Git merge management for parallel workers
│   ├── context-cache.py     # File caching for token optimization
│   ├── execution-logger.sh  # Structured execution logging (SI-001)
│   ├── failure-classifier.py  # Failure classification taxonomy (SI-002)
│   ├── pattern-clusterer.py # Failure pattern clustering (SI-003)
│   ├── root-cause-analyzer.py # Root cause analysis engine (SI-004)
│   ├── gap-generalizer.py   # Capability gap generalizer (SI-005)
│   ├── improvement-prd-generator.py # PRD generator from gaps (SI-006)
│   ├── improvement-manager.sh # PRD review interface (SI-007)
│   ├── gap-analysis-daemon.sh # Background gap analysis daemon (SI-008)
│   └── improvement-validator.py # Improvement validation suite (SI-009)
├── agents/              # Bundled agent prompts (tier 1)
├── docs/                # Documentation
├── skills/              # Claude Code skill definitions
└── .claude-loop/        # Runtime data (gitignored)
    ├── runs/            # Per-run metrics and reports
    │   └── {timestamp}/ # Individual run directory
    │       ├── metrics.json      # Per-iteration metrics
    │       ├── summary.json      # Run summary
    │       ├── improvements.json # Agent improvement suggestions
    │       └── report.html       # Beautiful HTML report
    ├── improvements/    # Generated improvement PRDs (SI-006)
    │   └── improve-*.json # Individual improvement PRDs
    ├── validation_reports/ # Validation reports (SI-009)
    │   └── {prd_name}_{timestamp}.json # Individual validation reports
    ├── held_out_cases/  # Held-out failure cases for validation (SI-009)
    │   └── {gap_id}.json # Cases per gap
    ├── daemon.log       # Daemon activity log (SI-008)
    ├── daemon_status.json # Current daemon status (SI-008)
    ├── daemon.pid       # Process ID file (SI-008)
    └── daemon.lock      # Lock file/directory (SI-008)
```

## Common Commands

```bash
# Run claude-loop with default settings
./claude-loop.sh

# Run with external agents for more specialists
./claude-loop.sh --agents-dir ~/claude-agents

# Run with verbose output
./claude-loop.sh -v

# Run with custom iteration limit
./claude-loop.sh -m 20
```

## Discovered Patterns

### Shell Script Portability
- Use `perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'` for millisecond timestamps on macOS
- Linux can use `date +%s%N` but macOS date doesn't support nanoseconds
- Use `bc` for floating point arithmetic in bash

### Monitoring Integration
- lib/monitoring.sh should be sourced at the start of claude-loop.sh
- Call `start_monitoring` at run start (also initializes JSON logging)
- Call `start_iteration(story_id)` before each iteration
- Call `track_iteration(story_id, tokens_in, tokens_out, status, agents_used)` after each iteration completes
- Call `end_monitoring` at run end (saves metrics.json and summary.json)

### JSON Logging Functions
- `init_json_logging()` - Creates .claude-loop/runs/{timestamp}/ directory
- `log_iteration_json(...)` - Appends iteration data to metrics array
- `save_metrics_json()` - Writes current metrics to metrics.json (called incrementally)
- `save_summary_json()` - Writes final summary to summary.json
- `enable_json_logging()` / `disable_json_logging()` - Control JSON output
- `get_run_directory()` / `get_metrics_file()` - Get paths for external use

### HTML Report Functions
- `generate_html_report()` - Generates report.html in run directory (requires Python 3)
- `enable_html_report()` / `disable_html_report()` - Control HTML report generation
- `get_report_file()` - Get path to generated HTML report
- Report includes: cost breakdown, story status, iteration details, lessons learned, improvement suggestions

### Agent Improvement Functions
- `run_agent_improver()` - Runs agent-improver.py to analyze run for improvement suggestions
- `get_improvements_file()` - Get path to generated improvements.json
- Improvement analysis includes:
  - Common failure patterns
  - Capability gaps from learnings
  - Performance outliers (slow/expensive iterations)
  - Suggested AGENTS.md updates
- Report generator automatically includes improvements in HTML reports

### Pricing Constants
- Opus pricing: $15/M input tokens, $75/M output tokens
- Update PRICE_INPUT_PER_M and PRICE_OUTPUT_PER_M in lib/monitoring.sh if pricing changes

## Lessons Learned from Self-Improvement Audit (2026-01-14)

### Performance Bottlenecks Identified
- **Excessive jq calls**: PRD validation spawned 220 jq processes for 20 stories (1-2s overhead)
  - Fix: Batch jq queries - use single pass with combined field checks
  - Expected improvement: 80-90% reduction (1-2s → 100-200ms)

- **Subprocess spawns**: Model selection, bc calculations repeated unnecessarily
  - Fix: Pre-compute model assignments for entire batch
  - Fix: Cache cost calculations or use bash arithmetic
  - Expected improvement: 90% reduction in spawn overhead

- **No log rotation**: 28MB+ accumulated logs without cleanup
  - Fix: Rotate logs at 10MB, gzip old logs, cleanup workers >30 days
  - Expected improvement: 70% disk usage reduction

- **O(n²) algorithms**: Dependency graph uses inefficient topological sort
  - Fix: Use heapq for priority queue, set for membership checks
  - Expected improvement: 70% reduction for large PRDs (50+ stories)

**See:** `docs/audits/performance-audit.md` for complete analysis and optimization roadmap

### Security Vulnerabilities Fixed
- **Command injection** (CVSS 9.8): `subprocess.run(shell=True)` enabled arbitrary command execution
  - Fix: Use `shell=False` with `shlex.split()`, add command whitelist
  - Attack vectors prevented: command chaining, substitution, pipe attacks

- **Path traversal** (CVSS 9.1): Symlink-based path traversal bypassed sandbox
  - Fix: Use `os.path.realpath()` to resolve symlinks before validation
  - Attack vectors prevented: `../../../etc/passwd`, symlink bypass, TOCTOU

- **Webhook injection** (CVSS 8.0): `eval` with user-controlled URLs
  - Fix: Replace eval with bash arrays, proper variable quoting
  - Attack vectors prevented: URL injection, payload injection

**See:** `docs/audits/security-audit.md` for complete vulnerability assessment

### Code Quality Improvements
- **Input validation**: 30+ validation checks added (CLI args, PRD fields, dependencies)
  - All user-provided data now validated at startup (fail fast)
  - Helpful error messages with context and platform-specific instructions

- **Error handling**: Bare except clauses fixed, specific exception types added
  - Improved debugging visibility (SystemExit/KeyboardInterrupt no longer caught)
  - Context-aware error messages with suggestions

- **Race conditions**: TOCTOU fixed with file locking (flock)
  - Prevents data corruption in multi-instance deployments
  - Parallel execution mode is now safe for concurrent workers

**See:** `CHANGELOG-improvements.md` for complete implementation details

### Code Organization Findings
- **Duplicate code**: 365 lines of duplicate code identified across 5 patterns
  - jq PRD parsing (120 lines) - extract to shared function
  - Error formatting (85 lines) - consolidate into lib/common-utils.sh
  - Timestamp generation (60 lines) - single source of truth
  - File locking (55 lines) - reusable lock wrapper
  - JSON validation (45 lines) - shared validation library

- **Oversized files**: 9 files exceed 1000 lines (technical debt)
  - claude-loop.sh: 2,890 lines (needs refactoring into modules)
  - lib/prd-manager.py: 1,662 lines (split into smaller modules)
  - Consider breaking into focused modules with single responsibility

**See:** `docs/audits/code-organization-audit.md` for refactoring recommendations

### Documentation Best Practices
- **Python**: Use Google-style docstrings with Args, Returns, Raises, Example sections
- **Shell**: Structured comment blocks with Arguments, Returns, Example, Notes sections
- **Inline comments**: Document complex logic, edge cases, and non-obvious workarounds
- **Configuration**: Centralize environment variable documentation

**See:** `docs/DOCUMENTATION-STYLE-GUIDE.md` for complete style guide

### Testing Strategy
- **Empirical validation**: Prove performance issues with benchmarks before optimizing
- **Before/after comparison**: Measure actual improvements (not just theoretical)
- **Anti-bloat protection**: Track LOC and complexity to prevent optimization bloat
- **Minimum thresholds**: Critical ≥50%, High ≥30%, Medium ≥15% improvement required

**See:** `tests/performance/README.md` for testing framework

### Key Patterns to Follow
1. **Validate inputs early**: Fail fast at startup, don't wait for cryptic errors later
2. **Batch subprocess calls**: Pre-compute and cache to avoid repeated spawns
3. **Use file locking**: Prevent race conditions in concurrent file access
4. **Quote shell variables**: Always quote `"$var"` to prevent word splitting
5. **Specific exception types**: Never use bare `except:`, catch specific errors
6. **Document assumptions**: Complex algorithms need overview before implementation
7. **Test with empirical data**: Prove issues exist with real benchmarks

### Anti-Patterns to Avoid
1. ❌ **Unvalidated user input**: Always validate CLI args, PRD fields, file paths
2. ❌ **shell=True**: Use shell=False with explicit argument arrays
3. ❌ **Bare except clauses**: Catch specific exceptions (ValueError, IOError, etc.)
4. ❌ **Repeated subprocess spawns**: Cache or batch operations
5. ❌ **Unquoted variables**: `$var` causes word splitting, use `"$var"`
6. ❌ **Unbounded loops**: Add iteration limits and timeout protection
7. ❌ **Missing error context**: Errors should explain what failed and how to fix it
8. ❌ **Assumed dependencies**: Check for jq, python3, git at startup
9. ❌ **No log rotation**: Implement cleanup to prevent unbounded growth
10. ❌ **Optimizing without proof**: Benchmark first, then optimize

---

## Gotchas & Warnings

### macOS Compatibility
- Don't use `date +%N` - not supported on macOS
- Use `wc -c` with `tr -d ' '` to trim whitespace on macOS (different output format)

### Bash Arithmetic
- Bash only supports integer arithmetic natively
- Always use `bc` for decimal/floating point calculations
- Use `echo "scale=N; expression" | bc` for precision control

### PRD Parser Integration
- Source lib/prd-parser.sh to get PRD validation and query functions
- Use `validate_prd "prd.json"` to validate PRD structure before running
- Use `get_ready_stories` to get stories ready to execute (deps satisfied)
- Use `get_story_dependencies "$story_id"` to get dependencies for a story
- Use `check_circular_dependencies` to detect circular deps (returns non-zero if cycles found)

### PRD Schema v2 (Parallelization)
Story-level fields (all optional for backward compatibility):
- `dependencies`: Array of story IDs this story depends on
- `fileScope`: Array of file paths this story modifies
- `estimatedComplexity`: simple|medium|complex
- `suggestedModel`: haiku|sonnet|opus (model override)

Top-level parallelization config (optional):
- `parallelization.enabled`: boolean (default: true)
- `parallelization.maxWorkers`: positive integer (default: 3)
- `parallelization.defaultModel`: haiku|sonnet|opus
- `parallelization.modelStrategy`: auto|always-opus|always-sonnet|always-haiku

### Dependency Graph Integration
- `python3 lib/dependency-graph.py plan prd.json` - Show execution plan
- `python3 lib/dependency-graph.py plan prd.json --json` - JSON output
- `python3 lib/dependency-graph.py check-cycles prd.json` - Verify no cycles
- `python3 lib/dependency-graph.py batches prd.json` - Get parallel batches as JSON
- `./claude-loop.sh --show-plan` - Preview execution plan without running

### Model Selector Integration
- `python3 lib/model-selector.py analyze prd.json` - Show model recommendations for all stories
- `python3 lib/model-selector.py select <story_id> prd.json` - Select model for specific story
- `python3 lib/model-selector.py select <story_id> prd.json --verbose` - Show selection reasoning
- `python3 lib/model-selector.py estimate-savings prd.json` - Estimate cost savings vs Opus
- `--model-strategy auto|always-opus|always-sonnet|always-haiku` - Override selection strategy

Model Pricing (per 1M tokens):
- Haiku:  $0.25 input, $1.25 output (~60x cheaper than Opus)
- Sonnet: $3.00 input, $15.00 output (~5x cheaper than Opus)
- Opus:   $15.00 input, $75.00 output (baseline)

Complexity Heuristics (weighted scoring):
- File scope count: 25% - More files = higher complexity
- Acceptance criteria: 25% - More criteria = higher complexity
- Keywords: 30% - Security/architecture keywords = complex, docs/config = simple
- Description length: 10% - Longer descriptions = more complex
- Dependencies: 10% - More dependencies = higher complexity

### Worker Process Isolation
- `./lib/worker.sh <story_id>` - Execute single story in isolation
- `./lib/worker.sh <story_id> --json` - JSON output for programmatic use
- `./lib/worker.sh <story_id> --model opus` - Override model selection
- `./lib/worker.sh <story_id> --timeout 300` - Set timeout in seconds

Worker Features:
- Isolated working directory per worker: `.claude-loop/workers/{story_id}_{timestamp}/`
- Separate log files: `logs/output.log`, `logs/error.log`, `logs/combined.log`
- Saves prompt for debugging: `logs/prompt.txt`
- Returns structured JSON result with success/failure, tokens, files changed
- Handles timeouts gracefully (uses `timeout` on Linux, `gtimeout` on macOS)
- Passes model selection to Claude CLI via `--model` flag

Worker Result Format (JSON):
```json
{
  "story_id": "US-001",
  "success": true,
  "exit_code": 0,
  "duration_ms": 12345,
  "tokens_in": 5000,
  "tokens_out": 2000,
  "model": "sonnet",
  "log_file": ".claude-loop/workers/US-001/logs/combined.log",
  "files_changed": ["path/to/file.ts"],
  "error": null,
  "timestamp": "2026-01-10T12:00:00Z"
}
```

Success Markers (checked in output):
- `WORKER_SUCCESS: <story_id>` - Explicit success
- `WORKER_FAILURE: <story_id>: <reason>` - Explicit failure
- `<loop>COMPLETE</loop>` - Standard completion signal

### Parallel Group Executor Integration
- `./lib/parallel.sh execute "US-001,US-002" --max-workers 3` - Execute stories in parallel
- `./lib/parallel.sh all --max-workers 4` - Execute all batches from dependency graph
- `source lib/parallel.sh && execute_parallel_group "US-001,US-002"` - Source and use functions
- `./claude-loop.sh --parallel --max-workers 4` - Run claude-loop in parallel mode

Parallel Execution Features:
- Launches workers as background processes for concurrent execution
- Limits parallelism via `--max-workers` flag (default: 3)
- Waits for all workers in a batch to complete before next batch
- Collects and aggregates results from all workers
- Displays real-time progress bar with completion status
- File-based worker tracking for bash 3.x compatibility (macOS)

Parallel Execution Flow:
1. Get batches from `dependency-graph.py` (stories with satisfied dependencies)
2. For each batch, launch up to `max_workers` workers concurrently
3. Display progress bar: `[██▓▓░░░] 2/5 complete | 2 running | 1 pending`
4. Collect results as workers complete
5. Move to next batch when current batch finishes
6. Aggregate and display final summary

### Merge Controller Integration
- `python3 lib/merge-controller.py check-conflicts prd.json` - Check file conflicts
- `python3 lib/merge-controller.py split-groups prd.json` - Split into parallel-safe groups
- `python3 lib/merge-controller.py can-parallel "US-001,US-002" prd.json` - Check if stories can run together
- `python3 lib/merge-controller.py create-branch US-001 --base main` - Create worker branch
- `python3 lib/merge-controller.py merge <branch> --base main` - Merge worker branch back
- `python3 lib/merge-controller.py cleanup --older-than 24h` - Clean up old worker branches
- `python3 lib/merge-controller.py list-branches` - List all worker branches
- `python3 lib/merge-controller.py lock-status` - Show file lock status

Merge Controller Features:
- File locking with `fcntl` to prevent concurrent file access
- Worker branch naming: `worker/{story_id}_{timestamp}`
- Rebase strategy for clean sequential merging
- Conflict detection before parallel execution starts
- Automatic fallback to sequential when file scopes overlap
- Branch cleanup with age-based and merge-based options

Conflict Detection:
- Compares `fileScope` arrays between stories
- Stories with overlapping files are placed in separate parallel groups
- Returns exit code 1 if conflicts detected (for scripting)
- JSON output available for programmatic consumption

Worker Branch Workflow:
1. Create worker branch from base: `create-branch <story_id>`
2. Worker executes story on isolated branch
3. On success, rebase onto latest base: `merge <branch>`
4. Clean up worker branch after merge
5. Fallback: if rebase fails, abort and report conflict

### Context Cache Integration
- `python3 lib/context-cache.py get <file>` - Get cached file hash
- `python3 lib/context-cache.py changed <file>` - Check if file changed since last cache
- `python3 lib/context-cache.py get-changed <files...>` - Get list of changed files
- `python3 lib/context-cache.py warm <files...>` - Pre-populate cache with files
- `python3 lib/context-cache.py stats --json` - Get cache statistics
- `python3 lib/context-cache.py clear` - Clear all cache entries
- `./claude-loop.sh --no-cache` - Disable file content caching

Context Cache Features:
- SHA256 hash-based content change detection
- mtime-based cache invalidation (fast check before hash)
- Persistent cache storage in `.claude-loop/cache/`
- Cache hit/miss tracking for metrics
- Estimated token savings reported in monitoring summary

Cache Statistics (in monitoring):
- `cache.hits` - Number of cache hits
- `cache.misses` - Number of cache misses
- `cache.hit_rate` - Hit rate percentage
- `cache.saved_tokens_estimate` - Estimated tokens saved from cache hits

Usage in monitoring.sh:
```bash
source lib/monitoring.sh
track_cache_hit 1000  # Track hit with estimated tokens saved
track_cache_miss       # Track cache miss
update_cache_stats     # Sync with context-cache.py stats
display_cache_stats    # Show cache stats in terminal
get_cache_stats_json   # Get stats as JSON
```

### Prompt Compressor Integration
- `python3 lib/prompt-compressor.py compress <story_id> prd.json` - Get compressed context
- `python3 lib/prompt-compressor.py estimate <story_id> prd.json` - Estimate token savings
- `python3 lib/prompt-compressor.py file-refs <story_id> prd.json` - Get file references
- `python3 lib/prompt-compressor.py summarize-progress progress.txt` - Summarize iterations
- `./claude-loop.sh --full-context` - Disable prompt compression

Prompt Compression Features:
- Filters files to story.fileScope only (not all project files)
- Summarizes previous iterations instead of including full progress.txt
- References unchanged files by content hash (saves tokens)
- Estimates token savings before/after compression
- Integrates with context-cache.py for change detection

Compression Benefits:
- Reduces prompt size by 20-40% typically
- Focuses context on story-relevant files
- Keeps key learnings from previous iterations
- Uses hash references for unchanged files

CLI Flags:
- `--full-context` - Disable all compression
- `--max-iterations N` - Limit iteration summary (default: 5)
- `--json` - Output as JSON for scripting

### Parallel Execution Metrics Integration
Monitoring tracks parallel execution statistics in real-time and includes them in reports.

Functions in lib/monitoring.sh:
```bash
enable_parallel_tracking    # Enable parallel stats collection
disable_parallel_tracking   # Disable parallel stats collection
track_parallel_batch $batch_size $batch_duration_ms $max_concurrent  # Track batch completion
track_sequential_estimate $story_duration_ms  # Add to sequential time estimate
get_parallel_speedup        # Get speedup factor (e.g., "2.5")
get_parallel_time_saved_ms  # Get time saved in milliseconds
get_parallel_stats_json     # Get stats as JSON object
display_parallel_stats      # Display stats in terminal
```

Metrics tracked:
- `parallel.enabled` - Whether parallel execution was used
- `parallel.batches` - Number of parallel batches executed
- `parallel.workers_used` - Total workers used
- `parallel.max_concurrent` - Maximum concurrent workers
- `parallel.parallel_time_ms` - Actual execution time
- `parallel.sequential_estimate_ms` - Estimated sequential time
- `parallel.time_saved_ms` - Time saved by parallelization
- `parallel.speedup_factor` - Speedup factor (sequential/parallel)

Dashboard API endpoint:
- `/api/parallel-stats` - Aggregate parallel stats across all runs

HTML Report includes:
- Optimization Stats section with model usage, cost savings, cache stats
- Parallel speedup metrics (if parallel execution enabled)
- Time comparison: sequential vs parallel vs saved

### Execution Logger Integration
- `source lib/execution-logger.sh` - Load logging functions
- `log_execution_start "SI-001" "Story Title" '{"context": "data"}'` - Start logging
- `log_action "Read" '{"file_path": "/path/to/file"}' "success" ""` - Log tool action
- `log_retry` - Increment retry count
- `log_fallback "reason"` - Log fallback attempt
- `log_execution_end "success" "" "0"` - Complete logging

Execution Log Storage:
- Location: `.claude-loop/execution_log.jsonl` (append-only JSONL format)
- Each entry contains: story_id, timestamp_start/end, duration_ms, status, error_type, error_message, attempted_actions, tools_used, file_types, context, retry_count, fallback_count

Error Type Classification:
- `timeout` - Execution exceeded time limit
- `not_found` - File, resource, or tool not found
- `permission` - Permission denied errors
- `parse` - JSON/syntax parsing errors
- `network` - Network/API connection errors
- `validation` - Test or validation failures
- `unknown` - Unclassified errors

CLI Commands:
- `./lib/execution-logger.sh stats` - Summary statistics
- `./lib/execution-logger.sh recent 5` - Last N executions
- `./lib/execution-logger.sh story SI-001` - Executions for story
- `./lib/execution-logger.sh failures` - Failure counts by error type
- `./lib/execution-logger.sh since 2026-01-01T00:00:00Z` - Since date
- `./lib/execution-logger.sh count` - Total execution count

### Failure Classifier Integration
- `python3 lib/failure-classifier.py classify <line_number>` - Classify a specific log entry
- `python3 lib/failure-classifier.py batch-classify` - Classify all failures
- `python3 lib/failure-classifier.py batch-classify --since 2026-01-01` - Classify since date
- `python3 lib/failure-classifier.py analyze` - Show classification summary statistics
- `python3 lib/failure-classifier.py categories` - List all failure categories

Failure Categories:
- `success` - Execution completed successfully
- `task_failure` - Task requirements are impossible or contradictory
- `capability_gap` - Missing capability that should be added
- `transient_error` - Temporary issue (network, timeout) - retry may help
- `unknown` - Cannot confidently classify

Classification Heuristics:
- **Pattern Matching**: Error messages matched against regex patterns for each category
- **Historical Frequency**: Repeated same error (3+ times) = likely capability gap
- **Context Analysis**: UI context + 'not found' = likely capability gap
- **Retry Analysis**: Multiple retries still failing = likely capability gap
- **Story History**: Story failed 3+ times = likely capability gap

Classification Output:
```json
{
  "category": "capability_gap",
  "confidence": 0.85,
  "reasoning": "Classified as capability gap...",
  "contributing_factors": ["UI context with 'not found'", "Error occurred 3 times"],
  "suggested_action": "Add UI automation capability for this interaction"
}
```

Usage in Self-Improvement Pipeline:
1. Execution logger writes JSONL entries
2. Failure classifier categorizes each failure
3. Capability gaps are fed to pattern clusterer (SI-003)
4. Root cause analyzer performs 5-Whys (SI-004)
5. Gap generalizer creates improvement categories (SI-005)

### Pattern Clusterer Integration
- `python3 lib/pattern-clusterer.py analyze` - Analyze failures and create patterns
- `python3 lib/pattern-clusterer.py analyze --min-occurrences 2` - Lower threshold
- `python3 lib/pattern-clusterer.py list` - List all discovered patterns
- `python3 lib/pattern-clusterer.py show <pattern_id>` - Show pattern details
- `python3 lib/pattern-clusterer.py summary` - Show summary statistics

Pattern Clustering Features:
- Groups similar failures by error_type and message similarity
- Normalizes error messages (removes paths, timestamps, IDs, numbers)
- Uses fuzzy text matching (SequenceMatcher) with 80% similarity threshold
- Requires minimum 3 occurrences by default to form a pattern
- Automatically merges highly similar patterns

FailurePattern Dataclass:
```python
@dataclass
class FailurePattern:
    pattern_id: str         # PAT-XXXXXXXX (hash-based)
    description: str        # Human-readable description
    error_type: str         # From execution logger
    normalized_message: str # Normalized error message
    occurrences: int        # Number of matching failures
    first_seen: str         # ISO timestamp
    last_seen: str          # ISO timestamp
    affected_stories: list  # Story IDs affected
    example_failures: list  # Up to 3 example entries
    context_indicators: list  # Common context/tools
```

CLI Output (JSON):
```json
{
  "pattern_id": "PAT-CC4BC15E",
  "description": "'not_found' failures involving not found",
  "error_type": "not_found",
  "normalized_message": "file <PATH> not found",
  "occurrences": 3,
  "affected_stories": ["SI-001", "SI-002", "SI-003"],
  "context_indicators": ["tool:Read"]
}
```

### Root Cause Analyzer Integration
- `python3 lib/root-cause-analyzer.py analyze <pattern_id>` - Analyze a pattern
- `python3 lib/root-cause-analyzer.py analyze <pattern_id> --no-llm` - Heuristic-only mode
- `python3 lib/root-cause-analyzer.py analyze <pattern_id> --no-cache` - Skip cache
- `python3 lib/root-cause-analyzer.py list` - List patterns available for analysis
- `python3 lib/root-cause-analyzer.py batch-analyze` - Analyze all patterns
- `python3 lib/root-cause-analyzer.py cache-stats` - Show cache statistics
- `python3 lib/root-cause-analyzer.py clear-cache` - Clear cached analyses
- `python3 lib/root-cause-analyzer.py mark-resolved <pattern_id> "<resolution>"` - Mark pattern as resolved

Root Cause Analyzer Features:
- 5-Whys decomposition on failure patterns
- LLM-assisted analysis with persistent caching
- Heuristic-only mode for offline analysis (--no-llm)
- Counterfactual analysis ("What capability would prevent this?")
- References similar past patterns that were resolved
- Cache stored in `.claude-loop/analysis_cache/`

RootCauseAnalysis Dataclass:
```python
@dataclass
class RootCauseAnalysis:
    pattern_id: str           # Pattern that was analyzed
    whys: list[str]           # List of 5 "why" decomposition steps
    root_cause: str           # Identified root cause
    capability_gap: str       # Specific capability that is missing
    counterfactual: str       # What would have prevented this?
    confidence: float         # Confidence score 0-1
    similar_patterns: list    # Past patterns that were resolved
    analysis_method: str      # "llm" or "heuristic"
    timestamp: str            # When analysis was performed
```

Root Cause Categories (heuristic detection):
- `missing_tool` - Required tool/handler not available
- `ui_automation` - UI interaction capability is limited
- `permission` - Insufficient permissions for operation
- `network` - Network connectivity issues
- `parsing` - Input format issues
- `file_handling` - File system operation failures
- `state_management` - Application state issues
- `api_interaction` - API interaction failures

CLI Output (JSON):
```json
{
  "pattern_id": "PAT-CC4BC15E",
  "whys": [
    "The UI interaction failed because the element could not be located",
    "The element could not be located because UI automation is limited",
    "UI automation is limited because visual detection is incomplete",
    "Visual detection is incomplete because multi-platform support is challenging",
    "Multi-platform support is challenging because UI frameworks vary significantly"
  ],
  "root_cause": "UI automation capability is limited or unavailable",
  "capability_gap": "UI interaction and visual automation",
  "counterfactual": "Robust UI automation with element detection and interaction",
  "confidence": 0.6,
  "similar_patterns": [],
  "analysis_method": "heuristic",
  "timestamp": "2026-01-11T17:00:00"
}
```

### Gap Generalizer Integration
- `python3 lib/gap-generalizer.py generalize <pattern_id>` - Generalize a pattern to capability gap
- `python3 lib/gap-generalizer.py generalize <pattern_id> --json` - JSON output
- `python3 lib/gap-generalizer.py list` - List all capability gaps
- `python3 lib/gap-generalizer.py show <gap_id>` - Show gap details
- `python3 lib/gap-generalizer.py registry` - Show registry summary
- `python3 lib/gap-generalizer.py prioritize` - Show gaps by priority
- `python3 lib/gap-generalizer.py batch-generalize` - Generalize all patterns
- `python3 lib/gap-generalizer.py categories` - List capability categories
- `python3 lib/gap-generalizer.py mark-resolved <gap_id> "resolution"` - Mark gap as resolved
- `python3 lib/gap-generalizer.py mark-deferred <gap_id> "reason"` - Mark gap as deferred

Gap Generalizer Features:
- Maps root cause analyses to 10 capability categories
- Calculates priority: (frequency * 0.35 + impact * 0.40 + feasibility * 0.25) * 100
- Identifies task families affected by each gap
- Estimates future failures if gap is not addressed
- Maintains gap registry in `.claude-loop/capability_gaps.json`
- Automatic gap merging for similar descriptions (>70% similarity)
- Status tracking: active, resolved, deferred

Capability Categories:
- `UI_INTERACTION` - GUI automation, visual verification (feasibility: 30%)
- `FILE_HANDLING` - File processing, directory management (feasibility: 90%)
- `NETWORK` - Web scraping, API consumption (feasibility: 70%)
- `PARSING` - Data transformation, format conversion (feasibility: 80%)
- `TOOL_INTEGRATION` - External tool invocation, CI/CD (feasibility: 70%)
- `STATE_MANAGEMENT` - Multi-step workflows, sessions (feasibility: 60%)
- `PERMISSION_HANDLING` - System admin, security operations (feasibility: 50%)
- `API_INTERACTION` - Third-party integrations, webhooks (feasibility: 70%)
- `ERROR_RECOVERY` - Fault-tolerant operations, retries (feasibility: 80%)
- `VALIDATION` - Input validation, data quality checks (feasibility: 90%)

Priority Score Components:
- `frequency_score` (35%): Based on pattern occurrence count (0-1)
- `impact_score` (40%): Based on number of affected stories (0-1)
- `feasibility_score` (25%): Based on category difficulty (0-1)

GeneralizedGap Dataclass:
```python
@dataclass
class GeneralizedGap:
    gap_id: str              # GAP-XXXXXXXX (hash-based)
    category: str            # One of CapabilityCategory values
    description: str         # Gap description
    affected_task_types: list[str]  # Task families affected
    priority_score: float    # Combined priority (0-100)
    frequency_score: float   # Based on occurrence count (0-1)
    impact_score: float      # Based on affected stories (0-1)
    feasibility_score: float # Based on category (0-1)
    root_cause_ids: list[str]  # Source RCA IDs
    pattern_ids: list[str]     # Source pattern IDs
    affected_stories: list[str]
    estimated_future_failures: float
    improvement_benefit: str
    created_at: str
    updated_at: str
    status: str              # active, resolved, deferred
```

CLI Output (JSON):
```json
{
  "gap_id": "GAP-A1B2C3D4",
  "category": "UI_INTERACTION",
  "description": "UI interaction and visual automation. Root cause: UI automation capability is limited",
  "affected_task_types": ["GUI automation", "Desktop application testing", "Visual verification"],
  "priority_score": 52.5,
  "frequency_score": 0.6,
  "impact_score": 0.5,
  "feasibility_score": 0.3,
  "root_cause_ids": ["PAT-CC4BC15E"],
  "pattern_ids": ["PAT-CC4BC15E"],
  "affected_stories": ["SI-001", "SI-002"],
  "estimated_future_failures": 4.5,
  "improvement_benefit": "Addressing this significant gap in ui interaction would improve success rates for: GUI automation, Desktop application testing, Visual verification. Expected reduction in failures: 30%.",
  "status": "active"
}
```

Usage in Self-Improvement Pipeline:
1. Execution logger writes JSONL entries (SI-001)
2. Failure classifier categorizes each failure (SI-002)
3. Pattern clusterer groups similar failures (SI-003)
4. Root cause analyzer performs 5-Whys (SI-004)
5. Gap generalizer creates capability categories (SI-005)
6. **Improvement PRD generator creates PRDs (SI-006)**

### Improvement PRD Generator Integration
- `python3 lib/improvement-prd-generator.py generate <gap_id>` - Generate PRD from gap
- `python3 lib/improvement-prd-generator.py generate <gap_id> --json` - JSON output
- `python3 lib/improvement-prd-generator.py generate <gap_id> --min-stories 7 --max-stories 12` - Control story count
- `python3 lib/improvement-prd-generator.py list` - List all PRDs
- `python3 lib/improvement-prd-generator.py list --status pending_review` - Filter by status
- `python3 lib/improvement-prd-generator.py show <prd_name>` - Show PRD details
- `python3 lib/improvement-prd-generator.py pending` - List PRDs pending review
- `python3 lib/improvement-prd-generator.py summary` - Show PRD summary
- `python3 lib/improvement-prd-generator.py approve <prd_name>` - Approve for implementation
- `python3 lib/improvement-prd-generator.py reject <prd_name> --reason "..."` - Reject with reason
- `python3 lib/improvement-prd-generator.py start <prd_name>` - Mark as in progress
- `python3 lib/improvement-prd-generator.py complete <prd_name>` - Mark as complete

Improvement PRD Generator Features:
- Generates 5-15 user stories per capability gap (configurable)
- Stories are generalizable (not specific to one use case)
- Includes test cases in acceptance criteria
- Sets story dependencies based on logical order
- Assigns complexity (simple/medium/complex) and model (haiku/sonnet/opus)
- Saves PRDs to `.claude-loop/improvements/` with status=pending_review
- Supports full PRD lifecycle: pending_review -> approved -> in_progress -> complete

PRD Status Workflow:
```
pending_review -> approved -> in_progress -> complete
                 \-> rejected
```

PRD Storage:
- Location: `.claude-loop/improvements/<prd-name>.json`
- Each PRD contains: name, project, branchName, description, gap_id, priority_score
- UserStories contain: id, title, description, acceptanceCriteria, priority, dependencies
- Story metadata: fileScope, estimatedComplexity, suggestedModel, passes, notes

ImprovementPRD Dataclass:
```python
@dataclass
class ImprovementPRD:
    name: str                    # e.g., "improve-file-handling-804113"
    project: str                 # e.g., "claude-loop-improvement-file_handling"
    branchName: str              # e.g., "feature/improve-file-handling-804113"
    description: str
    gap_id: str                  # Source gap ID
    gap_category: str            # Category from gap
    priority_score: float        # Gap priority score
    userStories: list[UserStory]
    status: str                  # pending_review, approved, rejected, in_progress, complete
    created_at: str
    updated_at: str
    reviewed_at: str             # When approved/rejected
    reviewer_notes: str
    estimated_effort: str        # Small/Medium/Large
    affected_task_types: list[str]
    source_patterns: list[str]
```

UserStory Dataclass:
```python
@dataclass
class UserStory:
    id: str                      # e.g., "IMP-001"
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    dependencies: list[str]      # Story IDs this depends on
    fileScope: list[str]         # Files this story will modify
    estimatedComplexity: str     # simple, medium, complex
    suggestedModel: str          # haiku, sonnet, opus
    passes: bool                 # Completion status
    notes: str
```

Story Templates by Category:
- Each capability category has pre-defined story templates
- Templates include: title, description, acceptance criteria, complexity, model
- Templates are customized based on gap specifics
- Test cases are included in acceptance criteria for all stories

Story Dependency Assignment:
- Each story depends on the previous story (sequential flow)
- Complex stories may depend on simpler prerequisite stories
- Dependencies ensure logical implementation order

### Improvement Review Interface Integration (SI-007)
CLI commands in claude-loop.sh for reviewing and managing improvement PRDs:

```bash
# List all improvement PRDs
./claude-loop.sh --list-improvements

# Review a specific PRD in detail
./claude-loop.sh --review-improvement <prd_name>

# Approve a PRD for implementation
./claude-loop.sh --approve-improvement <prd_name> --notes "Optional notes"

# Reject a PRD with reason
./claude-loop.sh --reject-improvement <prd_name> --reason "Reason required"

# Execute an approved PRD with claude-loop
./claude-loop.sh --execute-improvement <prd_name>

# View improvement history
./claude-loop.sh --improvement-history
```

Standalone improvement-manager.sh CLI:
```bash
# List with status filter
./lib/improvement-manager.sh list --status pending_review

# Summary statistics
./lib/improvement-manager.sh summary

# JSON output for scripting
./lib/improvement-manager.sh list --json
./lib/improvement-manager.sh review <prd_name> --json

# Direct status updates
./lib/improvement-manager.sh start <prd_name>
./lib/improvement-manager.sh complete <prd_name>
```

PRD Status Lifecycle:
```
pending_review -> approved -> in_progress -> complete
              \-> rejected
```

Improvement History:
- Stored in `.claude-loop/improvement_history.jsonl`
- JSONL format (one JSON object per line)
- Tracks: prd_name, action, details, timestamp
- Actions: approved, rejected, started, completed, execution_started, execution_completed

Execute Improvement Workflow:
1. Checks PRD exists and is approved
2. Marks PRD as in_progress
3. Backs up current prd.json if exists
4. Copies improvement PRD to prd.json
5. Runs claude-loop.sh with the improvement PRD
6. Marks PRD as complete on success
7. Logs execution outcome to history

### Gap Analysis Daemon Integration (SI-008)
Background daemon for autonomous gap analysis without blocking active work.

CLI commands in claude-loop.sh:
```bash
# Start the daemon in background
./claude-loop.sh --start-daemon

# Stop the running daemon
./claude-loop.sh --stop-daemon

# Check daemon status
./claude-loop.sh --daemon-status
```

Standalone daemon CLI:
```bash
# Start daemon
./lib/gap-analysis-daemon.sh start

# Stop daemon
./lib/gap-analysis-daemon.sh stop

# Check status
./lib/gap-analysis-daemon.sh status

# Run analysis once (foreground, no daemon)
./lib/gap-analysis-daemon.sh run-once
```

Configuration (environment variables):
- `DAEMON_INTERVAL_SECONDS`: Analysis interval (default: 3600 = 1 hour)
- `DAEMON_LOG_THRESHOLD`: New log entries to trigger (default: 10)
- `DAEMON_AUTO_GENERATE_PRD`: Auto-generate PRDs for new gaps (default: true)

Daemon Features:
- Periodic analysis at configurable interval
- Triggers on time OR new log entry count (whichever comes first)
- Lockfile prevents multiple daemon instances
- Graceful shutdown on SIGTERM/SIGINT
- Status tracking in `.claude-loop/daemon_status.json`
- Activity logging to `.claude-loop/daemon.log`

Analysis Pipeline (run periodically):
1. Pattern Clustering - Groups similar failures
2. Root Cause Analysis - 5-Whys decomposition (heuristic mode)
3. Gap Generalization - Maps to capability categories
4. PRD Generation - Creates improvement PRDs for new gaps

Daemon Status JSON:
```json
{
  "status": "running",
  "message": "Waiting for next analysis cycle",
  "timestamp": "2026-01-12T10:00:00Z",
  "pid": 12345,
  "config": {
    "interval_seconds": 3600,
    "log_threshold": 10,
    "auto_generate_prd": true
  },
  "last_run": "2026-01-12T09:00:00Z",
  "next_run": "2026-01-12T10:00:00Z",
  "stats": {
    "patterns_found": 5,
    "gaps_found": 2,
    "prds_generated": 1
  }
}
```

### Improvement Validator Integration (SI-009)
Validates improvement PRDs before deployment to prevent regressions and ensure quality.

CLI commands in claude-loop.sh:
```bash
# Validate a PRD before deployment
./claude-loop.sh --validate-improvement <prd_name>

# Validate with force (bypass blocking conditions)
./claude-loop.sh --validate-improvement <prd_name> --force

# Execute with pre-deployment validation
./claude-loop.sh --execute-improvement <prd_name> --validate

# Force execution despite validation failures
./claude-loop.sh --execute-improvement <prd_name> --validate --force
```

Standalone Python CLI:
```bash
# Validate a PRD
python3 lib/improvement-validator.py validate <prd_path>

# Validate with JSON output
python3 lib/improvement-validator.py validate <prd_path> --json

# Force validation to pass
python3 lib/improvement-validator.py validate <prd_path> --force

# Check existing test suite
python3 lib/improvement-validator.py check-tests

# Check capability coverage
python3 lib/improvement-validator.py check-coverage

# List validation reports
python3 lib/improvement-validator.py reports

# Add a held-out failure case
python3 lib/improvement-validator.py add-held-out <gap_id> "case name" --test-command "command"
```

Validation Checks:
1. **Existing Test Suite**: Must pass (no regressions)
2. **Improvement-Specific Tests**: Tests from PRD fileScope must pass
3. **Held-Out Cases**: Failure cases that should now succeed
4. **Capability Coverage**: Coverage should not decrease

ValidationResult Dataclass:
```python
@dataclass
class ValidationResult:
    prd_name: str
    prd_path: str
    validated_at: str
    existing_tests: TestSuiteResult | None
    improvement_tests: TestSuiteResult | None
    held_out_cases: TestSuiteResult | None
    coverage_before: CoverageMetrics | None
    coverage_after: CoverageMetrics | None
    passed: bool
    blocked: bool
    forced: bool
    blocking_reasons: list[str]
    warnings: list[str]
    summary: str
```

Blocking Conditions:
- Existing tests have failures (regression)
- Improvement-specific tests have failures

Non-Blocking Warnings:
- Held-out cases still failing
- Coverage decreased

Validation Reports:
- Stored in `.claude-loop/validation_reports/`
- Named: `{prd_name}_{timestamp}.json`
- Contains full validation results with test details

Held-Out Cases:
- Stored in `.claude-loop/held_out_cases/{gap_id}.json`
- JSON array of cases with name and optional test_command
- Cases that were failing before improvement, expected to pass after

Self-Improvement Pipeline Integration:
```
1. Gap Analysis -> Generate PRD (SI-006)
2. Review PRD -> Approve (SI-007)
3. Validate PRD -> Check tests/coverage (SI-009)
4. Execute PRD -> Implement improvement
5. Rollback if needed (SI-012)
```

### Health Indicators Integration (SCALE-011)
Leading indicator metrics to predict problems before they manifest.

CLI commands:
```bash
# Show all indicators with RAG status
python3 lib/health-indicators.py status

# Show status as JSON
python3 lib/health-indicators.py --json status

# Show trend over time
python3 lib/health-indicators.py history --days 30

# Show active alerts
python3 lib/health-indicators.py alerts

# Acknowledge an alert
python3 lib/health-indicators.py acknowledge <alert_id>

# View/set thresholds
python3 lib/health-indicators.py thresholds --show
python3 lib/health-indicators.py thresholds --set proposal_rate_change.amber_max=1.8

# Run health check (returns exit code 2 on RED, 1 on AMBER, 0 on GREEN)
python3 lib/health-indicators.py check --json

# View specific indicator
python3 lib/health-indicators.py proposal-rate-change --verbose
```

Leading Indicators:
- `proposal_rate_change`: Ratio of improvement proposals vs baseline (>2x spike = RED)
- `cluster_concentration`: Fraction of failures in dominant pattern (>60% = RED)
- `retrieval_miss_rate`: Fraction of unhelpful experience retrievals (>50% = RED)
- `domain_drift`: Fraction of work in unknown domains (>40% = RED)

Each indicator has:
- `value`: Current numeric value
- `status`: RAG status (green/amber/red/unknown)
- `trend`: Direction (improving/stable/degrading)
- `message`: Human-readable description

Alert System:
- Alerts created automatically when RED/AMBER thresholds crossed
- Alerts resolved when status returns to GREEN
- Acknowledgment tracking for human review
- Stored in `.claude-loop/health_alerts.json`

History and Persistence:
- Health snapshots saved to `.claude-loop/health_history.jsonl`
- Threshold config stored in `.claude-loop/health_config.json`

Dashboard API Endpoints:
- `GET /api/health-indicators` - Get current health snapshot
- `GET /api/health-indicators/alerts` - Get active alerts
- `GET /api/health-indicators/history?days=30&indicator=<name>` - Get history

### Calibration Tracker Integration (SCALE-012)
Measures system alignment with human decisions over time to determine when
autonomous promotion can be enabled.

Key principle: Earn autonomy through demonstrated calibration, not assumption.
- 95% agreement threshold over 50+ decisions
- 6-month minimum parallel evaluation period
- Blocking autonomous mode until threshold met

CLI commands:
```bash
# Show current calibration status
python3 lib/calibration-tracker.py status

# Show status as JSON
python3 lib/calibration-tracker.py --json status

# Show calibration history
python3 lib/calibration-tracker.py history --days 30

# Show disagreements between system and human
python3 lib/calibration-tracker.py disagreements
python3 lib/calibration-tracker.py disagreements --type false_positive
python3 lib/calibration-tracker.py disagreements --type false_negative

# Check if autonomous mode is allowed
python3 lib/calibration-tracker.py autonomous-check

# Generate weekly calibration report
python3 lib/calibration-tracker.py weekly-report
python3 lib/calibration-tracker.py weekly-report --list
python3 lib/calibration-tracker.py weekly-report --show <filename>

# Save current state snapshot
python3 lib/calibration-tracker.py snapshot
```

Data Sources:
- `.claude-loop/improvement_decisions.jsonl` - Improvement queue decisions
- `.claude-loop/cluster_decisions.jsonl` - Pattern clustering decisions
- `.claude-loop/promotion_decisions.jsonl` - Promotion decisions

Calibration Metrics:
- `agreement_rate`: Overall system-human agreement rate (0.0-1.0)
- `false_positive_rate`: System said approve, human rejected
- `false_negative_rate`: System said reject, human approved
- `by_source`: Metrics broken down by decision source
- `by_domain`: Metrics broken down by domain
- `by_confidence`: Metrics broken down by confidence level
- `recent_trend`: Agreement rate in last 30 days

Calibration Status:
- `calibrating`: Building history, not enough data
- `on_track`: Meeting threshold, building history
- `at_risk`: Below threshold (85-95%), may recover
- `failing`: Consistently below 85% threshold
- `qualified`: Meets all requirements for autonomous mode

Autonomous Mode Requirements:
- 95% agreement rate
- 50+ decisions
- 180+ days evaluation period
- All requirements must be met simultaneously

History and Persistence:
- Calibration snapshots saved to `.claude-loop/calibration_history.jsonl`
- State stored in `.claude-loop/calibration_state.json`
- Weekly reports in `.claude-loop/calibration_reports/`

Dashboard API Endpoints:
- `GET /api/calibration` - Get current calibration metrics
- `GET /api/calibration/history?days=30` - Get calibration history
- `GET /api/calibration/disagreements?days=90&type=<type>` - Get disagreements
- `GET /api/calibration/autonomous-check` - Check autonomous eligibility
- `GET /api/calibration/weekly-report` - Generate weekly report
- `GET /api/calibration/weekly-report?list=true` - List available reports
- `GET /api/calibration/weekly-report?show=<filename>` - Get specific report
