# Configuration Guide

Complete configuration reference for the Claude-Loop autonomous coding extension.

## Configuration File Location

User configuration: `~/.epiloop/config/autonomous-coding.json`

Default configuration: `extensions/claude-loop/config/defaults.json`

## Configuration Schema

```json
{
  "qualityGates": {
    "requireTests": true,
    "requireTypecheck": true,
    "requireLint": true,
    "minCoverage": 75,
    "securityScan": true
  },
  "execution": {
    "maxConcurrent": 3,
    "timeout": 3600000,
    "maxMemoryPerTask": 512,
    "maxDiskPerTask": 1024
  },
  "workspace": {
    "cleanupDays": 30,
    "maxConcurrentPerUser": 3
  },
  "reporting": {
    "verbosity": "normal",
    "batchDelay": 2000
  },
  "improvement": {
    "autoGenerateProposals": true,
    "minPatternFrequency": 3,
    "reportPeriod": "monthly"
  },
  "claudeLoop": {
    "path": "/path/to/claude-loop",
    "workspaceRoot": "~/.epiloop/workspaces/autonomous-coding"
  }
}
```

## Configuration Options

### Quality Gates

Controls code quality validation before marking stories complete.

**`qualityGates.requireTests`** (boolean, default: `true`)
- Require test suite to pass before story completion
- Recommended: `true` for production code

**`qualityGates.requireTypecheck`** (boolean, default: `true`)
- Require TypeScript type checking to pass
- Runs `tsc --noEmit`

**`qualityGates.requireLint`** (boolean, default: `true`)
- Require linting to pass
- Uses oxlint

**`qualityGates.minCoverage`** (number, default: `75`)
- Minimum test coverage percentage (0-100)
- Story fails if coverage below this threshold

**`qualityGates.securityScan`** (boolean, default: `true`)
- Run security vulnerability scan (npm audit)

### Execution

Controls autonomous execution behavior.

**`execution.maxConcurrent`** (number, default: `3`)
- Maximum number of concurrent autonomous tasks
- Higher values use more system resources
- Minimum: 1

**`execution.timeout`** (number, default: `3600000`)
- Execution timeout in milliseconds
- Default: 1 hour (3600000ms)
- Minimum: 60000ms (1 minute)

**`execution.maxMemoryPerTask`** (number, default: `512`)
- Maximum memory per task in MB
- Used for resource monitoring

**`execution.maxDiskPerTask`** (number, default: `1024`)
- Maximum disk space per task in MB
- Workspaces exceeding this may be flagged

### Workspace

Controls workspace management and cleanup.

**`workspace.cleanupDays`** (number, default: `30`)
- Automatically delete workspaces older than this many days
- Minimum: 1

**`workspace.maxConcurrentPerUser`** (number, default: `3`)
- Maximum concurrent sessions per user
- Prevents resource exhaustion from single user
- Minimum: 1

### Reporting

Controls progress reporting behavior.

**`reporting.verbosity`** (string, default: `"normal"`)
- Verbosity level for progress messages
- Options: `"minimal"`, `"normal"`, `"detailed"`
- `minimal`: Essential updates only
- `normal`: Story progress and key events
- `detailed`: Full execution logs and debug info

**`reporting.batchDelay`** (number, default: `2000`)
- Delay in milliseconds between batched progress updates
- Higher values reduce message frequency
- Lower values provide more real-time updates
- Minimum: 1000ms

### Improvement

Controls self-improvement and learning behavior.

**`improvement.autoGenerateProposals`** (boolean, default: `true`)
- Automatically generate improvement proposals from failure patterns
- Set to `false` to disable automatic proposal generation

**`improvement.minPatternFrequency`** (number, default: `3`)
- Minimum occurrences of failure pattern before generating proposal
- Higher values reduce noise from random failures

**`improvement.reportPeriod`** (string, default: `"monthly"`)
- Frequency of self-improvement reports
- Options: `"daily"`, `"weekly"`, `"monthly"`

### Claude Loop

Controls claude-loop integration.

**`claudeLoop.path`** (string, required)
- Path to claude-loop installation
- Must be absolute path to claude-loop directory
- Example: `/Users/username/Documents/Projects/claude-loop`

**`claudeLoop.workspaceRoot`** (string, default: `"~/.epiloop/workspaces/autonomous-coding"`)
- Root directory for autonomous coding workspaces
- Supports `~` expansion for home directory
- Each session creates isolated subdirectory

## Environment-Specific Configuration

### Development

```json
{
  "execution": {
    "maxConcurrent": 1,
    "timeout": 7200000
  },
  "reporting": {
    "verbosity": "detailed"
  },
  "improvement": {
    "minPatternFrequency": 1
  }
}
```

### Production

```json
{
  "qualityGates": {
    "minCoverage": 80,
    "securityScan": true
  },
  "execution": {
    "maxConcurrent": 5,
    "timeout": 3600000
  },
  "reporting": {
    "verbosity": "normal"
  }
}
```

### CI/CD

```json
{
  "execution": {
    "maxConcurrent": 1,
    "timeout": 1800000
  },
  "reporting": {
    "verbosity": "minimal"
  },
  "workspace": {
    "cleanupDays": 1
  }
}
```

## Configuration Validation

Configuration is automatically validated on load. Common validation errors:

**`minCoverage must be between 0 and 100`**
- Coverage percentage out of range
- Fix: Set value between 0-100

**`timeout must be at least 60000ms`**
- Timeout too short
- Fix: Increase to at least 1 minute (60000ms)

**`Claude-loop path does not exist`**
- Invalid claude-loop installation path
- Fix: Update `claudeLoop.path` to correct location

**`maxConcurrent must be at least 1`**
- Invalid concurrent limit
- Fix: Set to 1 or higher

## Creating User Configuration

1. Create config directory:
```bash
mkdir -p ~/.epiloop/config
```

2. Create configuration file:
```bash
cat > ~/.epiloop/config/autonomous-coding.json << 'EOF'
{
  "execution": {
    "maxConcurrent": 5,
    "timeout": 7200000
  },
  "reporting": {
    "verbosity": "detailed"
  }
}
EOF
```

3. Test configuration:
```bash
epiloop autonomous-coding status
```

## Programmatic Configuration

For testing or custom integrations:

```typescript
import { loadConfig, getDefaultConfig } from "@epiloop/claude-loop/config";

// Load user configuration with defaults
const config = loadConfig();

// Get defaults only (useful for testing)
const defaults = getDefaultConfig();

// Override specific values
const customConfig = {
  ...defaults,
  execution: {
    ...defaults.execution,
    maxConcurrent: 1,
  },
};
```

## Configuration Precedence

1. User configuration (`~/.epiloop/config/autonomous-coding.json`)
2. Default configuration (`config/defaults.json`)
3. Environment variables (not currently supported)

User configuration values override defaults on a per-field basis.

## Troubleshooting

**Config not loading**
- Check file permissions: `chmod 644 ~/.epiloop/config/autonomous-coding.json`
- Verify JSON syntax: `cat ~/.epiloop/config/autonomous-coding.json | jq .`
- Check logs: `~/.epiloop/logs/claude-loop/`

**Tasks timing out**
- Increase `execution.timeout`
- Check system resources
- Reduce `execution.maxConcurrent`

**High memory usage**
- Reduce `execution.maxConcurrent`
- Decrease `execution.maxMemoryPerTask`
- Enable workspace cleanup

## Best Practices

1. **Start Conservative**: Begin with low `maxConcurrent` and increase gradually
2. **Monitor Resources**: Use system monitoring to tune memory/CPU limits
3. **Regular Cleanup**: Keep `workspace.cleanupDays` at reasonable value (7-30 days)
4. **Coverage Goals**: Set `minCoverage` based on project requirements (75-90%)
5. **Timeouts**: Adjust `timeout` based on project complexity
6. **Verbosity**: Use `detailed` for debugging, `normal` for production
7. **Security**: Always keep `securityScan` enabled in production
