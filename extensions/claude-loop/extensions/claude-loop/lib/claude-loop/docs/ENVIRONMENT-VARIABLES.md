# Environment Variables Reference

Complete reference for all environment variables used in claude-loop.

## Quick Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | - | Anthropic API key |
| `CLAUDE_LOOP_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `CLAUDE_LOOP_MAX_ITERATIONS` | No | `100` | Maximum iterations |
| `CLAUDE_LOOP_PARALLEL_MAX_WORKERS` | No | `3` | Parallel worker limit |
| `DAEMON_INTERVAL_SECONDS` | No | `3600` | Gap analysis interval |
| `DAEMON_LOG_THRESHOLD` | No | `10` | Logs to trigger analysis |
| `DAEMON_AUTO_GENERATE_PRD` | No | `true` | Auto-generate improvement PRDs |

---

## Required Variables

### ANTHROPIC_API_KEY

**Type:** String (API key format: `sk-ant-...`)

**Required:** Yes

**Description:**
Anthropic API key for Claude API access. Required for all LLM operations.

**Example:**
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
./claude-loop.sh prd.json
```

**Security:**
- ⚠️ Never commit to version control
- Store in `.env` file (add to `.gitignore`)
- Or store in system environment/secrets manager
- Rotate regularly (every 90 days recommended)

**Error if missing:**
```
❌ ANTHROPIC_API_KEY environment variable not set
Please set your API key:
  export ANTHROPIC_API_KEY="sk-ant-..."
Or create a .env file with: ANTHROPIC_API_KEY=sk-ant-...
```

**Used by:**
- All Claude API calls
- `lib/agent_runtime.py`
- Model selection and execution
- Experience retrieval with embeddings

---

## Logging & Debugging

### CLAUDE_LOOP_LOG_LEVEL

**Type:** String enum (`DEBUG` | `INFO` | `WARN` | `ERROR`)

**Required:** No

**Default:** `INFO`

**Description:**
Controls logging verbosity across all modules.

**Levels:**
- `DEBUG`: Maximum verbosity - all operations logged
- `INFO`: Standard logging - key events only
- `WARN`: Warnings and errors only
- `ERROR`: Errors only

**Example:**
```bash
# Maximum verbosity for debugging
CLAUDE_LOOP_LOG_LEVEL=DEBUG ./claude-loop.sh prd.json

# Quiet mode (errors only)
CLAUDE_LOOP_LOG_LEVEL=ERROR ./claude-loop.sh prd.json
```

**Performance Impact:**
- `DEBUG`: ~10% slower (extensive logging)
- `INFO`: Minimal impact (<1%)
- `WARN`/`ERROR`: Negligible

**Used by:**
- `lib/structured-logging.sh`
- All modules that emit logs
- Python logging configuration

---

### CLAUDE_LOOP_VERBOSE

**Type:** Boolean (`true` | `false` | `1` | `0`)

**Required:** No

**Default:** `false`

**Description:**
Legacy verbose flag. Equivalent to `LOG_LEVEL=DEBUG`.

**Example:**
```bash
CLAUDE_LOOP_VERBOSE=true ./claude-loop.sh prd.json
```

**Note:** Deprecated - use `CLAUDE_LOOP_LOG_LEVEL=DEBUG` instead.

---

## Execution Control

### CLAUDE_LOOP_MAX_ITERATIONS

**Type:** Positive integer

**Required:** No

**Default:** `100`

**Description:**
Maximum number of iterations before automatic stop. Safety limit to prevent infinite loops.

**Example:**
```bash
# Run for max 50 iterations
CLAUDE_LOOP_MAX_ITERATIONS=50 ./claude-loop.sh prd.json

# Unlimited (not recommended)
CLAUDE_LOOP_MAX_ITERATIONS=999999 ./claude-loop.sh prd.json
```

**Recommendations:**
- Development: 10-20 iterations
- Production: 50-100 iterations
- Long-running: 200-500 iterations

**Warning:** Values >1000 will trigger a warning at startup.

**Used by:**
- `claude-loop.sh` main iteration loop
- Monitoring and safety checks

---

### CLAUDE_LOOP_DELAY_SECONDS

**Type:** Non-negative number (supports decimals)

**Required:** No

**Default:** `0`

**Description:**
Delay between iterations in seconds. Useful for rate limit management.

**Example:**
```bash
# 2 second delay between iterations
CLAUDE_LOOP_DELAY_SECONDS=2 ./claude-loop.sh prd.json

# Half-second delay
CLAUDE_LOOP_DELAY_SECONDS=0.5 ./claude-loop.sh prd.json
```

**Use cases:**
- Rate limit protection
- Resource throttling
- Debugging (slow down execution)

**Used by:**
- `claude-loop.sh` main loop
- Worker launch coordination

---

## Parallel Execution

### CLAUDE_LOOP_PARALLEL_MAX_WORKERS

**Type:** Positive integer (1-10)

**Required:** No

**Default:** `3`

**Description:**
Maximum concurrent workers for parallel PRD execution.

**Example:**
```bash
# High parallelism (powerful machine)
CLAUDE_LOOP_PARALLEL_MAX_WORKERS=8 ./claude-loop.sh --parallel prd.json

# Sequential (single worker)
CLAUDE_LOOP_PARALLEL_MAX_WORKERS=1 ./claude-loop.sh --parallel prd.json
```

**Recommendations:**
- Laptops: 2-3 workers
- Desktops: 4-6 workers
- Servers: 6-10 workers
- CI/CD: 2-4 workers (resource limited)

**Resource impact:**
| Workers | CPU | Memory | API Calls/min |
|---------|-----|--------|---------------|
| 1 | 1 core | 500MB | 10-20 |
| 3 | 2-3 cores | 1.5GB | 30-60 |
| 8 | 4-6 cores | 4GB | 80-160 |

**Used by:**
- `lib/parallel.sh`
- Parallel batch executor

---

### CLAUDE_LOOP_PARALLEL_ENABLED

**Type:** Boolean (`true` | `false` | `1` | `0`)

**Required:** No

**Default:** `true` (if PRD has parallelization config)

**Description:**
Enable or disable parallel execution.

**Example:**
```bash
# Force sequential execution
CLAUDE_LOOP_PARALLEL_ENABLED=false ./claude-loop.sh prd.json
```

**Used by:**
- `lib/parallel.sh`
- PRD coordinator

---

## Model Selection

### CLAUDE_LOOP_DEFAULT_MODEL

**Type:** String enum (`haiku` | `sonnet` | `opus`)

**Required:** No

**Default:** `sonnet`

**Description:**
Default model for story execution if not specified in PRD.

**Example:**
```bash
# Use cheapest model by default
CLAUDE_LOOP_DEFAULT_MODEL=haiku ./claude-loop.sh prd.json

# Use best model by default
CLAUDE_LOOP_DEFAULT_MODEL=opus ./claude-loop.sh prd.json
```

**Model comparison:**
| Model | Cost | Speed | Quality |
|-------|------|-------|---------|
| Haiku | $ | Fast | Good |
| Sonnet | $$ | Medium | Better |
| Opus | $$$$ | Slow | Best |

**Used by:**
- `lib/model-selector.py`
- Worker execution

---

### CLAUDE_LOOP_MODEL_STRATEGY

**Type:** String enum (`auto` | `always-haiku` | `always-sonnet` | `always-opus`)

**Required:** No

**Default:** `auto`

**Description:**
Model selection strategy for automatic model assignment.

**Strategies:**
- `auto`: Smart selection based on story complexity
- `always-haiku`: Force haiku for all stories (cheap)
- `always-sonnet`: Force sonnet for all stories (balanced)
- `always-opus`: Force opus for all stories (quality)

**Example:**
```bash
# Cost optimization mode
CLAUDE_LOOP_MODEL_STRATEGY=always-haiku ./claude-loop.sh prd.json

# Quality mode
CLAUDE_LOOP_MODEL_STRATEGY=always-opus ./claude-loop.sh prd.json
```

**Used by:**
- `lib/model-selector.py`
- Cost estimation

---

## Self-Improvement System

### DAEMON_INTERVAL_SECONDS

**Type:** Positive integer

**Required:** No

**Default:** `3600` (1 hour)

**Description:**
Interval between gap analysis daemon runs (in seconds).

**Example:**
```bash
# Run analysis every 30 minutes
DAEMON_INTERVAL_SECONDS=1800 ./claude-loop.sh --start-daemon

# Run analysis every 4 hours
DAEMON_INTERVAL_SECONDS=14400 ./claude-loop.sh --start-daemon
```

**Recommendations:**
- Development: 300-900s (5-15 min)
- Production: 3600-7200s (1-2 hours)
- Low activity: 14400-86400s (4-24 hours)

**Used by:**
- `lib/gap-analysis-daemon.sh`

---

### DAEMON_LOG_THRESHOLD

**Type:** Positive integer

**Required:** No

**Default:** `10`

**Description:**
Number of new log entries to trigger gap analysis (whichever comes first: interval or threshold).

**Example:**
```bash
# Trigger analysis after 50 new logs
DAEMON_LOG_THRESHOLD=50 ./claude-loop.sh --start-daemon

# Only use time interval (set very high)
DAEMON_LOG_THRESHOLD=999999 ./claude-loop.sh --start-daemon
```

**Used by:**
- `lib/gap-analysis-daemon.sh`

---

### DAEMON_AUTO_GENERATE_PRD

**Type:** Boolean (`true` | `false` | `1` | `0`)

**Required:** No

**Default:** `true`

**Description:**
Automatically generate improvement PRDs for newly discovered capability gaps.

**Example:**
```bash
# Manual PRD generation only
DAEMON_AUTO_GENERATE_PRD=false ./claude-loop.sh --start-daemon
```

**Used by:**
- `lib/gap-analysis-daemon.sh`
- `lib/improvement-prd-generator.py`

---

## Testing & Development

### SKIP_PRD_VALIDATION

**Type:** Boolean (`true` | `false` | `1` | `0`)

**Required:** No

**Default:** `false`

**Description:**
Skip PRD validation for faster testing. **⚠️ NOT RECOMMENDED FOR PRODUCTION**

**Example:**
```bash
# Skip validation (testing only!)
SKIP_PRD_VALIDATION=true ./claude-loop.sh prd.json
```

**Warning:** May cause cryptic errors if PRD is invalid.

**Used by:**
- `lib/prd-parser.sh`
- `claude-loop.sh`

---

### CLAUDE_LOOP_DRY_RUN

**Type:** Boolean (`true` | `false` | `1` | `0`)

**Required:** No

**Default:** `false`

**Description:**
Dry-run mode: validate and plan without executing stories.

**Example:**
```bash
CLAUDE_LOOP_DRY_RUN=true ./claude-loop.sh prd.json
```

**Used by:**
- `claude-loop.sh`
- Worker execution

---

## Configuration Files

### Loading from .env

Create a `.env` file in the project root:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_LOOP_LOG_LEVEL=INFO
CLAUDE_LOOP_MAX_ITERATIONS=50
CLAUDE_LOOP_PARALLEL_MAX_WORKERS=4
DAEMON_INTERVAL_SECONDS=3600
```

Load before running:

```bash
# Source .env
source .env
./claude-loop.sh prd.json

# Or use dotenv tool
dotenv -f .env ./claude-loop.sh prd.json
```

**Security:** Add `.env` to `.gitignore`!

---

## Setting Variables

### Temporary (single run)

```bash
# Inline
VAR_NAME=value ./claude-loop.sh prd.json

# Export first
export VAR_NAME=value
./claude-loop.sh prd.json
```

### Persistent (shell session)

```bash
# Add to shell profile
echo 'export VAR_NAME=value' >> ~/.bashrc
source ~/.bashrc
```

### System-wide (all users)

```bash
# Add to /etc/environment (Linux)
sudo echo 'VAR_NAME=value' >> /etc/environment

# Or add to /etc/profile.d/
sudo echo 'export VAR_NAME=value' > /etc/profile.d/claude-loop.sh
```

---

## Debugging Variable Issues

### Check if variable is set

```bash
echo $VAR_NAME
env | grep VAR_NAME
printenv VAR_NAME
```

### Check variable in script

```bash
# Add debug output
./claude-loop.sh prd.json 2>&1 | grep -i "VAR_NAME"

# Or enable debug mode
CLAUDE_LOOP_LOG_LEVEL=DEBUG ./claude-loop.sh prd.json
```

### Common issues

**Variable not set:**
```bash
# Check typo in variable name
env | grep CLAUDE

# Check if .env was sourced
source .env && env | grep ANTHROPIC
```

**Variable has wrong value:**
```bash
# Check for trailing spaces
echo "$VAR_NAME" | cat -A

# Check for quotes
echo "$VAR_NAME" | od -c
```

---

## See Also

- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Documentation Style Guide](DOCUMENTATION-STYLE-GUIDE.md)
- [Configuration Reference](../docs/configuration.md)
