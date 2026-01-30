# Troubleshooting Guide

Common error patterns, root causes, and solutions for claude-loop issues.

## Table of Contents

1. [PRD Validation Errors](#prd-validation-errors)
2. [Dependency Issues](#dependency-issues)
3. [API and Authentication Errors](#api-and-authentication-errors)
4. [Parallel Execution Issues](#parallel-execution-issues)
5. [Phase 2 Tier 2 Integration Issues](#phase-2-tier-2-integration-issues)
6. [File Permission Errors](#file-permission-errors)
7. [Performance Issues](#performance-issues)
8. [State Corruption](#state-corruption)
9. [Common Failure Patterns](#common-failure-patterns)

---

## PRD Validation Errors

### Error: "PRD validation failed: Missing required field 'userStories'"

**Cause:** PRD JSON is missing the required `userStories` array.

**Solution:**
```bash
# Ensure your PRD has this structure:
{
  "project": "my-project",
  "branchName": "feature/my-feature",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "priority": 1,
      "passes": false
    }
  ]
}
```

**See:** `docs/prd-schema.md` for complete schema reference.

---

### Error: "Circular dependencies detected"

**Cause:** Story A depends on Story B, which depends on Story A (circular dependency chain).

**Diagnosis:**
```bash
# Check dependency graph
python3 lib/dependency-graph.py check-cycles prd.json

# Visualize dependencies
python3 lib/dependency-graph.py plan prd.json
```

**Solution:**
1. Identify the circular chain in the error output
2. Remove or reorganize dependencies to break the cycle
3. Consider whether dependencies are truly necessary

**Example circular chain:**
```
US-001 -> US-002 -> US-003 -> US-001  # BAD: cycle
```

**Fixed:**
```
US-001 -> US-002 -> US-003  # GOOD: linear dependencies
```

---

### Error: "Story US-XXX has invalid dependency: US-YYY"

**Cause:** A story references a dependency ID that doesn't exist in the PRD.

**Solution:**
1. Check that the dependency ID is spelled correctly
2. Verify the dependency story exists in userStories array
3. Ensure story IDs match the required format: `[A-Z]+-\d{3}`

```bash
# List all story IDs in PRD
jq -r '.userStories[].id' prd.json

# Check specific story dependencies
jq -r '.userStories[] | select(.id == "US-001") | .dependencies' prd.json
```

---

## Dependency Issues

### Error: "Missing required tools: jq"

**Cause:** Required command-line tools are not installed.

**Solution (macOS):**
```bash
brew install jq python3 git
```

**Solution (Linux - Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install jq python3 git bc curl
```

**Solution (Linux - RHEL/CentOS):**
```bash
sudo yum install jq python3 git bc curl
```

---

### Error: "Python 3.8+ required, found: 3.7.x"

**Cause:** Python version is too old.

**Solution (macOS):**
```bash
brew install python@3.11
```

**Solution (Linux - use pyenv):**
```bash
curl https://pyenv.run | bash
pyenv install 3.11.0
pyenv global 3.11.0
```

**Solution (Docker):**
```dockerfile
FROM python:3.11-slim
# ... rest of Dockerfile
```

---

### Error: "Required Python package not found: anthropic"

**Cause:** Python dependencies not installed.

**Solution:**
```bash
# Install all required packages
pip3 install -r requirements.txt

# Or install individually
pip3 install anthropic chromadb jinja2 requests
```

**Verify installation:**
```bash
python3 -c "import anthropic; print(anthropic.__version__)"
python3 -c "import chromadb; print(chromadb.__version__)"
```

---

## API and Authentication Errors

### Error: "ANTHROPIC_API_KEY environment variable not set"

**Cause:** API key not configured.

**Solution (temporary):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
./claude-loop.sh prd.json
```

**Solution (persistent - .env file):**
```bash
# Create .env file (add to .gitignore!)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Source before running
source .env
./claude-loop.sh prd.json
```

**Solution (persistent - shell profile):**
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

**Security Warning:** Never commit API keys to version control!

---

### Error: "401 Unauthorized" or "Invalid API Key"

**Cause:** API key is invalid or expired.

**Diagnosis:**
```bash
# Test API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'
```

**Solution:**
1. Verify API key is correct (no extra spaces/newlines)
2. Check API key is active in Anthropic Console
3. Generate new API key if necessary

---

### Error: "429 Too Many Requests" or "Rate Limit Exceeded"

**Cause:** API rate limit exceeded.

**Diagnosis:**
```bash
# Check current rate limit headers
# (shown in error response)
```

**Solution (immediate):**
```bash
# Wait and retry with delay
./claude-loop.sh --delay 2 prd.json  # 2 second delay between iterations
```

**Solution (long-term):**
1. Reduce parallel workers: `--max-workers 1`
2. Increase delay: `--delay 5`
3. Use cheaper models: `--model-strategy always-haiku`
4. Upgrade API tier if available

---

## Parallel Execution Issues

### Error: "File conflicts detected between stories"

**Cause:** Multiple stories modify the same files and can't run in parallel.

**Diagnosis:**
```bash
# Check conflict detection
python3 lib/merge-controller.py check-conflicts prd.json
```

**Solution:**
```bash
# Option 1: Run sequentially (automatic fallback)
./claude-loop.sh prd.json  # System will detect conflicts and run sequentially

# Option 2: Split into conflict-free groups
python3 lib/merge-controller.py split-groups prd.json

# Option 3: Adjust fileScope to be more specific
# Edit prd.json and narrow down fileScope arrays
```

---

### Error: "Worker timed out after 300s"

**Cause:** Story execution exceeded timeout limit.

**Solution (increase timeout):**
```bash
# Increase worker timeout
./lib/worker.sh US-001 --timeout 600  # 10 minutes
```

**Solution (optimize story):**
1. Break large story into smaller stories
2. Reduce scope of story tasks
3. Check for infinite loops or hanging operations

**Diagnosis:**
```bash
# Check worker logs for hang location
tail -f .claude-loop/workers/US-001_*/logs/combined.log
```

---

### Error: "Worker branch merge failed: conflicts"

**Cause:** Parallel workers created conflicting changes.

**Solution (automatic retry):**
```bash
# System will automatically retry sequentially
# No action needed
```

**Solution (manual resolution):**
```bash
# List worker branches
python3 lib/merge-controller.py list-branches

# Manually resolve conflicts
git checkout worker/US-001_timestamp
git rebase main
# Fix conflicts
git add .
git rebase --continue

# Merge manually
git checkout main
git merge worker/US-001_timestamp
```

---

## Phase 2 Tier 2 Integration Issues

### Error: "MCP server connection failed"

**Cause:** MCP server is not running or unreachable.

**Diagnosis:**
```bash
# Check MCP configuration
cat .claude-loop/mcp-config.json

# Test MCP server manually
python3 lib/mcp_client.py test-connection <server_name>

# Check server status
ps aux | grep mcp-server
```

**Solution:**
```bash
# Start MCP server (example: filesystem server)
npx @modelcontextprotocol/server-filesystem /path/to/directory &

# Or use Docker
docker run -d -p 8080:8080 mcp-server-filesystem

# Verify connection
./claude-loop.sh --list-mcp-tools
```

**See:** `docs/features/mcp-integration.md` for server setup guide.

---

### Error: "MCP tool not in whitelist"

**Cause:** Attempted to use MCP tool that's not in the configured whitelist.

**Expected Behavior:** This is intentional security protection.

**Solution:**
```bash
# Check whitelist configuration
jq '.servers[] | select(.name == "filesystem") | .tools_whitelist' .claude-loop/mcp-config.json

# Add tool to whitelist
# Edit .claude-loop/mcp-config.json:
{
  "servers": [{
    "name": "filesystem",
    "tools_whitelist": ["read_file", "list_directory"]  # Add your tool here
  }]
}

# Restart claude-loop to reload config
```

**Security Note:** Only whitelist tools you trust and understand.

---

### Error: "Provider API call failed: litellm.exceptions.RateLimitError"

**Cause:** Rate limit exceeded for LLM provider.

**Diagnosis:**
```bash
# Check provider usage
jq '.providers' lib/llm_providers.yaml

# View recent provider calls
tail -20 .claude-loop/logs/provider_usage.jsonl | jq '.'

# Check cost report
./claude-loop.sh --cost-report
```

**Solution (automatic fallback):**
```bash
# System will automatically fallback to secondary providers
# No action needed - check logs for fallback behavior
tail -f .claude-loop/logs/provider_usage.jsonl
```

**Solution (manual configuration):**
```bash
# Adjust provider priority in lib/llm_providers.yaml
providers:
  - name: openai
    priority: 2  # Lower priority to reduce usage
  - name: anthropic
    priority: 1  # Higher priority as fallback

# Add rate limit delays
--delay 3  # 3 second delay between iterations
```

---

### Error: "No provider available for requirements"

**Cause:** Story requires capabilities (vision, tools) that no enabled provider supports.

**Diagnosis:**
```bash
# Check story requirements
jq -r '.userStories[] | select(.id == "US-001") | .required_capabilities' prd.json

# Check provider capabilities
jq '.providers[] | {name, capabilities, enabled}' lib/llm_providers.yaml
```

**Solution:**
```bash
# Option 1: Enable provider with required capability
# Edit lib/llm_providers.yaml and set enabled: true for provider with vision/tools

# Option 2: Remove capability requirement from story
# If vision/tools not actually needed, remove from PRD

# Option 3: Use Claude fallback (always available)
# Claude Code CLI supports all capabilities
```

---

### Error: "Delegation depth limit (2) exceeded"

**Cause:** Attempted to delegate beyond MAX_DELEGATION_DEPTH=2.

**Expected Behavior:** This is intentional complexity protection.

**Diagnosis:**
```bash
# Check delegation hierarchy
cat .claude-loop/logs/delegation.jsonl | jq '.depth'

# Visualize delegation tree
python3 lib/delegation_visualizer.py show
```

**Solution:**
1. Flatten the task hierarchy (reduce nesting)
2. Combine subtasks to reduce delegation depth
3. Break complex story into multiple peer stories (no parent-child relationship)

**Example - Before (depth=3, WILL FAIL):**
```
Story A
  ├─ Subtask B (depth=1)
     └─ Subtask C (depth=2)
        └─ Subtask D (depth=3) ❌ BLOCKED
```

**Example - After (depth=2, OK):**
```
Story A
  ├─ Subtask B (depth=1)
  ├─ Subtask C (depth=1)
  └─ Subtask D (depth=1) ✓ OK
```

---

### Error: "Agent context budget (100k tokens) exceeded"

**Cause:** Delegation subtask context exceeds MAX_CONTEXT_PER_AGENT limit.

**Diagnosis:**
```bash
# Check delegation context sizes
jq '.context_size' .claude-loop/logs/delegation.jsonl

# Identify large context sources
grep "context_size" .claude-loop/logs/delegation.jsonl | sort -rn
```

**Solution:**
1. Simplify subtask description (reduce prompt size)
2. Limit fileScope for subtask (fewer files in context)
3. Use summarization for large file contexts
4. Split into smaller, focused subtasks

**Example configuration adjustment:**
```bash
# Increase limit if legitimately needed (not recommended)
export MAX_CONTEXT_PER_AGENT=150000  # 150k tokens

# Or reduce context in PRD
{
  "fileScope": ["specific-file.py"],  # Not entire src/
  "estimatedComplexity": "simple"      # Use simpler model
}
```

---

### Error: "Delegation cycle detected: US-001 → US-002 → US-001"

**Cause:** Circular delegation creates infinite loop.

**Expected Behavior:** This is prevented by cycle detection.

**Diagnosis:**
```bash
# Check delegation graph
python3 lib/delegation_tracker.py check-cycles

# Visualize delegation tree
jq '.delegation_graph' .claude-loop/logs/delegation.jsonl
```

**Solution:**
1. Break circular dependency (A delegates to B, B delegates to C, C does NOT delegate back to A)
2. Use shared subtasks instead of circular delegation
3. Restructure task hierarchy to be acyclic

**Prevention:** Design delegation as DAG (Directed Acyclic Graph), not cyclical.

---

### Issue: "Multi-provider cost savings lower than expected"

**Cause:** Provider selection not optimized for actual task complexity.

**Diagnosis:**
```bash
# Generate cost report
./claude-loop.sh --cost-report

# Check provider selection logic
jq '.complexity, .selected_provider' .claude-loop/logs/provider_usage.jsonl

# Compare actual vs estimated savings
python3 lib/cost_analyzer.py compare-phase1-phase2
```

**Solution:**
```bash
# Adjust complexity scoring in lib/provider_selector.py
# Lower complexity threshold for cheaper providers
--model-strategy always-haiku  # Force cheapest provider for testing

# Review story complexity assignments
jq '.userStories[] | {id, estimatedComplexity}' prd.json

# Use cost optimizer skill
./claude-loop.sh --skill cost-optimizer prd.json
```

**Expected Savings:** 30-50% reduction on diverse workloads. Simple tasks benefit most (70%+ savings).

---

### Issue: "Delegation creates too many subtasks"

**Cause:** Agent over-delegates, creating unnecessary complexity.

**Diagnosis:**
```bash
# Count delegation frequency
jq '.parent_story' .claude-loop/logs/delegation.jsonl | sort | uniq -c

# Check subtask sizes
jq '.estimatedHours' .claude-loop/logs/delegation.jsonl
```

**Solution:**
1. Add delegation guidelines to story description
2. Set minimum subtask size (e.g., "Only delegate tasks >2 hours")
3. Review delegation decisions in cost report
4. Disable delegation for simple stories

**Configuration:**
```bash
# Disable delegation for simple stories
export ENABLE_DELEGATION_MIN_COMPLEXITY=3  # Only complex stories (complexity>=3)

# Or disable entirely for specific PRD
./claude-loop.sh --disable-delegation prd.json
```

---

### Issue: "MCP tools slower than expected"

**Cause:** Network latency, large data transfers, or inefficient tool usage.

**Diagnosis:**
```bash
# Check MCP call latencies
jq '.latency_ms' .claude-loop/logs/mcp_calls.jsonl

# Identify slow tools
jq 'select(.latency_ms > 1000)' .claude-loop/logs/mcp_calls.jsonl
```

**Solution:**
```bash
# Use local MCP servers (not remote)
# Edit .claude-loop/mcp-config.json:
{
  "endpoint": "http://localhost:8080"  # Local, not remote
}

# Cache MCP tool results
export ENABLE_MCP_CACHE=true

# Limit MCP tool data transfer size
# Configure in tool parameters: max_results=100
```

**Performance Target:** MCP calls should complete in <500ms for local servers, <2s for remote.

---

### Rollback to Phase 1

**Scenario:** Phase 2 features causing issues, need to rollback.

**Solution (disable all Phase 2 features):**
```bash
# Disable all features via environment variables
export ENABLE_MCP=false
export ENABLE_MULTI_PROVIDER=false
export ENABLE_DELEGATION=false

./claude-loop.sh prd.json
```

**Solution (disable individual features):**
```bash
# Disable MCP only
./claude-loop.sh --disable-mcp prd.json

# Disable multi-provider only
./claude-loop.sh --disable-multi-provider prd.json

# Disable delegation only
./claude-loop.sh --disable-delegation prd.json
```

**Solution (git rollback):**
```bash
# Rollback to Phase 1 branch (if separate branch)
git checkout main  # Or phase1 branch
./claude-loop.sh prd.json  # Phase 1 only
```

**Verification:**
```bash
# Verify Phase 2 disabled
./claude-loop.sh --status | grep "Phase 2"

# Should show:
# MCP: disabled
# Multi-Provider: disabled
# Delegation: disabled
```

---

## File Permission Errors

### Error: "No write permission for .claude-loop directory"

**Cause:** Insufficient permissions to write to data directory.

**Solution:**
```bash
# Fix permissions
chmod -R u+w .claude-loop

# Or change ownership
sudo chown -R $USER:$USER .claude-loop
```

---

### Error: "Permission denied: /etc/passwd" or path traversal blocked

**Cause:** Story attempted to access files outside sandbox (security block).

**Expected Behavior:** This is intentional security protection.

**Solution:**
1. Verify the file path is within project directory
2. Check if symlinks are causing path resolution issues
3. Adjust sandbox boundaries if legitimately needed (not recommended)

**Diagnosis:**
```bash
# Check file path resolution
realpath /path/to/file

# Check if it's within project
echo "$PWD"
```

---

## Performance Issues

### Issue: "PRD validation takes 2+ seconds"

**Cause:** Excessive jq subprocess calls (Issue #1 from performance audit).

**Diagnosis:**
```bash
# Run performance benchmarks
./tests/performance/benchmark-suite.sh

# Check PRD parsing time
time bash -c "source lib/prd-parser.sh && validate_prd prd.json"
```

**Solution:**
Implement optimizations from `docs/audits/performance-audit.md`:
1. Batch jq calls (reduce 220 calls to 20)
2. Cache story data after first read
3. Use faster validation algorithms

**Workaround (temporary):**
```bash
# Skip validation for known-good PRDs
SKIP_PRD_VALIDATION=true ./claude-loop.sh prd.json  # NOT RECOMMENDED
```

---

### Issue: "Disk usage growing unbounded (28MB+)"

**Cause:** No log rotation (Issue #3 from performance audit).

**Diagnosis:**
```bash
# Check disk usage
du -sh .claude-loop
du -sh .claude-loop/workers
du -sh .claude-loop/runs
```

**Solution (manual cleanup):**
```bash
# Remove old worker logs
find .claude-loop/workers -type d -mtime +30 -exec rm -rf {} \;

# Compress old logs
find .claude-loop/workers -name "*.log" -mtime +7 -exec gzip {} \;

# Remove old runs
find .claude-loop/runs -type d -mtime +60 -exec rm -rf {} \;
```

**Solution (automated - coming soon):**
```bash
# Implement log rotation from performance audit
# See docs/audits/performance-audit.md Phase 1
```

---

### Issue: "Parallel execution slower than sequential"

**Cause:** Overhead from coordination, small stories, or limited parallelism.

**Diagnosis:**
```bash
# Check parallel metrics
jq '.parallel' .claude-loop/runs/*/summary.json

# Calculate actual speedup
python3 << 'EOF'
import json
with open('.claude-loop/runs/latest/summary.json') as f:
    data = json.load(f)
    speedup = data['parallel']['speedup_factor']
    print(f"Speedup: {speedup}x")
EOF
```

**Solution:**
1. Increase workers for more parallelism: `--max-workers 5`
2. Ensure stories have sufficient work to parallelize
3. Check for file conflicts causing sequential fallback
4. Use faster model for coordination: `--model haiku`

---

## State Corruption

### Error: "Invalid JSON in session-state.json"

**Cause:** Concurrent writes corrupted the state file (race condition).

**Diagnosis:**
```bash
# Check if JSON is valid
jq empty .claude-loop/session-state.json

# If invalid, check for partial writes
cat .claude-loop/session-state.json | head -20
```

**Solution (recover from backup):**
```bash
# Check for backup
ls -lt .claude-loop/session-state.json*

# Restore from backup if exists
cp .claude-loop/session-state.json.backup .claude-loop/session-state.json

# Or start fresh
rm .claude-loop/session-state.json
./claude-loop.sh --reset-state prd.json
```

**Prevention:**
- Use file locking (fixed in US-006 Phase 1)
- Avoid running multiple instances concurrently on same PRD
- Use separate branches for parallel work

---

### Error: "PRD has been modified externally, reload required"

**Cause:** PRD file changed while claude-loop was running.

**Solution:**
```bash
# Stop current execution (Ctrl+C)
# Restart with updated PRD
./claude-loop.sh prd.json
```

**Prevention:**
- Don't edit PRD while claude-loop is running
- Use version control (git) to track PRD changes
- Use separate PRD files for different features

---

## Common Failure Patterns

### Pattern: Stories fail with "File not found"

**Likely Causes:**
1. Story's fileScope references non-existent files
2. Worker directory isolation issue
3. Relative path resolution problem

**Debug Steps:**
```bash
# Check story fileScope
jq -r '.userStories[] | select(.id == "US-001") | .fileScope[]' prd.json

# Verify files exist
for file in $(jq -r '.userStories[0].fileScope[]' prd.json); do
  if [ ! -f "$file" ]; then
    echo "Missing: $file"
  fi
done

# Check worker logs
cat .claude-loop/workers/US-001_*/logs/combined.log
```

**Solution:**
1. Update fileScope to include correct paths
2. Create missing files if needed
3. Use absolute paths in fileScope

---

### Pattern: Tests pass locally but fail in claude-loop

**Likely Causes:**
1. Different working directory
2. Missing environment variables
3. Test depends on previous state

**Debug Steps:**
```bash
# Check working directory
pwd

# Check environment
env | grep CLAUDE

# Run tests manually from same context
cd .claude-loop/workers/US-001_*/
bash -c "pytest tests/"
```

**Solution:**
1. Ensure tests are hermetic (no external dependencies)
2. Pass environment variables to workers
3. Use absolute paths in test fixtures

---

### Pattern: "Command injection detected" but command is safe

**Likely Causes:**
1. Legitimate use of shell metacharacters
2. Overly strict validation rules

**Debug Steps:**
```bash
# Check command that triggered warning
grep "Command injection" .claude-loop/workers/*/logs/error.log

# Test command manually
bash -c "YOUR_COMMAND_HERE"
```

**Solution:**
1. Use safer command alternatives (avoid shell metacharacters)
2. Quote arguments properly
3. If legitimately needed, use explicit whitelist

**Example:**
```bash
# Instead of
bash -c "find . -name '*.log' | xargs rm"

# Use safer alternative
find . -name '*.log' -delete
```

---

## Getting More Help

### Enable Debug Logging

```bash
# Maximum verbosity
CLAUDE_LOOP_LOG_LEVEL=DEBUG ./claude-loop.sh prd.json

# Save debug log to file
CLAUDE_LOOP_LOG_LEVEL=DEBUG ./claude-loop.sh prd.json 2>&1 | tee debug.log
```

### Check Execution Logs

```bash
# Recent failures
./lib/execution-logger.sh recent 10

# Specific story failures
./lib/execution-logger.sh story US-001

# Failure patterns
python3 lib/failure-classifier.py analyze
```

### Run Diagnostics

```bash
# System health check
./lib/health-indicators.py status

# Performance benchmarks
./tests/performance/benchmark-suite.sh

# Configuration validation
./lib/config-validator.sh
```

### Report Issues

When reporting issues, include:

1. **Environment:** OS, Python version, shell version
2. **Command:** Exact command that failed
3. **Error output:** Complete error message
4. **PRD excerpt:** Relevant part of PRD (redact sensitive data)
5. **Logs:** Relevant excerpts from `.claude-loop/workers/*/logs/`

```bash
# Generate diagnostic report
{
  echo "=== Environment ==="
  uname -a
  python3 --version
  bash --version | head -1
  jq --version

  echo -e "\n=== Recent Errors ==="
  ./lib/execution-logger.sh recent 5

  echo -e "\n=== Disk Usage ==="
  du -sh .claude-loop

  echo -e "\n=== Git Status ==="
  git status --short
} > diagnostic-report.txt
```

Submit to: https://github.com/anthropics/claude-loop/issues

---

## Quick Reference

| Error Type | First Check | Quick Fix |
|------------|-------------|-----------|
| PRD validation | `jq . prd.json` | Fix JSON syntax |
| Missing dependency | `which jq python3 git` | Install tools |
| API authentication | `echo $ANTHROPIC_API_KEY` | Set API key |
| Permission denied | `ls -la .claude-loop` | Fix permissions |
| Worker timeout | Check logs | Increase timeout |
| Rate limit | Wait 60s | Add `--delay 5` |
| Disk full | `df -h` | Clean old logs |
| State corruption | `jq . session-state.json` | Restore backup |

---

**See Also:**
- [Documentation Style Guide](DOCUMENTATION-STYLE-GUIDE.md)
- [Performance Audit](audits/performance-audit.md)
- [Security Audit](audits/security-audit.md)
- [AGENTS.md](../AGENTS.md)
