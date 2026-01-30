# Claude-Loop Integration Architecture

Technical architecture documentation for the claude-loop autonomous coding integration.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Epiloop Core                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   WhatsApp   │  │   Telegram   │  │    Other     │     │
│  │   Channel    │  │   Channel    │  │   Channels   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         └──────────────────┴──────────────────┘             │
│                           │                                  │
│                  ┌────────▼────────┐                        │
│                  │  Skill Router   │                        │
│                  └────────┬────────┘                        │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              Claude-Loop Extension (Plugin)                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          AutonomousCodingSkill Handler               │  │
│  │  - Command parsing                                   │  │
│  │  - Session management                                │  │
│  │  - Event forwarding                                  │  │
│  └──────────┬───────────────────────────────────────────┘  │
│             │                                                │
│  ┌──────────▼───────────┐  ┌───────────────────────┐      │
│  │   PRD Generator      │  │  Workspace Manager    │      │
│  │  - Claude API        │  │  - Session isolation  │      │
│  │  - Context analysis  │  │  - Resource limits    │      │
│  └──────────┬───────────┘  └───────────┬───────────┘      │
│             │                            │                   │
│  ┌──────────▼────────────────────────────▼───────────┐    │
│  │              Loop Executor                         │    │
│  │  - Process spawning                                │    │
│  │  - Event streaming                                 │    │
│  │  - Checkpoint management                           │    │
│  └──────────┬─────────────────────────────────────────┘    │
│             │                                                │
│  ┌──────────▼───────────┐  ┌───────────────────────┐      │
│  │  Progress Reporter   │  │  Quality Gates        │      │
│  │  - Formatting        │  │  - Tests              │      │
│  │  - Batching          │  │  - Type checking      │      │
│  └──────────┬───────────┘  └───────────┬───────────┘      │
│             │                            │                   │
│  ┌──────────▼────────────────────────────▼───────────┐    │
│  │              Metrics Logger                        │    │
│  │  - Session tracking                                │    │
│  │  - Disk persistence                                │    │
│  └──────────┬─────────────────────────────────────────┘    │
│             │                                                │
│  ┌──────────▼───────────────────────────────────────┐      │
│  │         Improvement Engine                        │      │
│  │  - Pattern detection                              │      │
│  │  - Proposal generation                            │      │
│  └───────────────────────────────────────────────────┘      │
│                                                              │
│  ┌───────────────────────────────────────────────────┐     │
│  │         Experience Bridge                         │     │
│  │  - Vector search                                  │     │
│  │  - Learning from past implementations             │     │
│  └───────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. AutonomousCodingSkill Handler

**Purpose**: Main entry point for autonomous coding commands

**Responsibilities**:
- Parse user commands (/autonomous-coding start, status, etc.)
- Manage user sessions and workspace isolation
- Forward events to progress reporters
- Handle pause/resume/stop operations

**Key Interfaces**:
```typescript
interface CommandResult {
  success: boolean;
  message: string;
  sessionId?: string;
  data?: any;
}

class AutonomousCodingSkill {
  async handleCommand(command: string, params: any): Promise<CommandResult>
}
```

### 2. PRD Generator

**Purpose**: Convert natural language feature descriptions to structured PRDs

**Responsibilities**:
- Analyze codebase context (languages, frameworks, patterns)
- Generate user stories with acceptance criteria
- Define technical architecture
- Specify testing strategy

**Key Interfaces**:
```typescript
interface PRDFormat {
  title: string;
  epic: string;
  stories: UserStory[];
  technical_architecture: TechnicalArchitecture;
  testing_strategy: TestingStrategy;
}

async function convertMessageToPRD(
  message: string,
  context?: CodebaseContext
): Promise<PRDFormat>
```

### 3. Loop Executor

**Purpose**: Execute claude-loop process for autonomous implementation

**Responsibilities**:
- Spawn claude-loop.sh subprocess
- Stream execution events (progress, logs, errors)
- Handle checkpoints for pause/resume
- Monitor process health

**Key Interfaces**:
```typescript
class LoopExecutor extends EventEmitter {
  async start(prd: PRDFormat): Promise<void>
  async stop(options: StopOptions): Promise<void>
  async resume(): Promise<void>
  getStatus(): ExecutionStatus
}

// Events:
// - started: { sessionId, prd }
// - progress: { progress, currentStory, completedStories }
// - story-complete: { storyId, duration, passed }
// - error: { phase, error }
// - complete: { duration, completedStories, totalStories }
```

### 4. Workspace Manager

**Purpose**: Manage isolated workspaces for each session

**Responsibilities**:
- Create isolated workspace directories
- Track active sessions per user
- Enforce resource limits (max concurrent, disk, memory)
- Clean up old/abandoned sessions

**Key Interfaces**:
```typescript
interface Workspace {
  path: string;
  sessionId: string;
  userId: string;
  createdAt: Date;
}

class WorkspaceManager {
  async createWorkspace(userId: string, description: string): Promise<Workspace>
  async cleanupOldSessions(daysOld: number): Promise<void>
}
```

### 5. Quality Gates

**Purpose**: Validate code quality before marking stories complete

**Responsibilities**:
- Run test suites with coverage measurement
- Execute type checker (tsc --noEmit)
- Run linter (oxlint)
- Perform security scans (npm audit)

**Key Interfaces**:
```typescript
interface QualityGateResult {
  passed: boolean;
  gates: {
    tests?: { passed: boolean; coverage?: number };
    typecheck?: { passed: boolean; errors?: number };
    lint?: { passed: boolean; warnings?: number };
    security?: { passed: boolean; vulnerabilities?: number };
  };
}

class QualityGates {
  async validate(): Promise<QualityGateResult>
}
```

### 6. Progress Reporter

**Purpose**: Format and deliver progress updates to users

**Responsibilities**:
- Subscribe to LoopExecutor events
- Format messages with emojis and progress bars
- Batch updates (smart batching every 2 seconds)
- Support multiple verbosity levels

**Key Interfaces**:
```typescript
class ProgressReporter extends EventEmitter {
  subscribe(executor: LoopExecutor): void
  unsubscribe(): void
}

// Emits 'message' events with formatted strings
```

### 7. Parallel Coordinator

**Purpose**: Coordinate multiple concurrent autonomous coding tasks

**Responsibilities**:
- Queue management for pending tasks
- Enforce max concurrent limit (default: 3)
- Monitor resource usage per task
- Event forwarding for all tasks

**Key Interfaces**:
```typescript
interface TaskInfo {
  id: string;
  prd: PRDFormat;
  userId: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress?: number;
}

class ParallelCoordinator extends EventEmitter {
  async enqueue(prd: PRDFormat, userId: string): Promise<string>
  async cancel(taskId: string): Promise<boolean>
  getStats(): CoordinatorStats
}
```

### 8. Metrics Logger

**Purpose**: Track execution metrics for analysis and improvement

**Responsibilities**:
- Log session start/progress/completion
- Track story durations and outcomes
- Record quality gate results
- Monitor resource usage
- Persist metrics to disk

**Key Interfaces**:
```typescript
interface SessionMetrics {
  sessionId: string;
  userId: string;
  prdTitle: string;
  stories: StoryProgress[];
  errors: ErrorLog[];
  qualityGates: QualityGateLog[];
  resourceUsage: ResourceUsageLog[];
}

class MetricsLogger {
  async logExecutionStart(sessionId: string, metadata: SessionStartMetadata): Promise<void>
  async logStoryProgress(sessionId: string, progress: StoryProgress): Promise<void>
  async getAggregateStats(sessionId: string): Promise<AggregateStats>
}
```

### 9. Improvement Engine

**Purpose**: Learn from failures and generate improvement proposals

**Responsibilities**:
- Record failures with context
- Detect patterns in failures
- Generate improvement proposals
- Track success rate over time (calibration)
- Generate periodic reports

**Key Interfaces**:
```typescript
interface ImprovementProposal {
  id: string;
  title: string;
  description: string;
  reasoning: string;
  impact: "low" | "medium" | "high";
  status: "pending" | "approved" | "rejected" | "applied";
}

class ImprovementEngine {
  async recordFailure(failure: FailureRecord): Promise<void>
  async detectPatterns(): Promise<FailurePattern[]>
  async generateProposals(): Promise<ImprovementProposal[]>
  async getSuccessRate(): Promise<number>
}
```

### 10. Experience Bridge

**Purpose**: Connect to claude-loop's experience store for learning

**Responsibilities**:
- Search for relevant past implementations
- Store new experiences
- Provide feedback on experiences
- Query statistics

**Key Interfaces**:
```typescript
interface ExperienceEntry {
  domain: string;
  problem: string;
  solution: string;
  helpful: boolean;
  timestamp: Date;
}

class ExperienceBridge {
  async search(query: string, options?: ExperienceSearchOptions): Promise<ExperienceEntry[]>
  async store(problem: string, solution: string, domain: string): Promise<void>
}
```

## Data Flow

### Execution Flow

```
1. User sends command:
   "/autonomous-coding start 'Add user auth'"

2. Skill Handler:
   - Parses command
   - Creates workspace via WorkspaceManager
   - Generates PRD via PRDGenerator

3. Loop Executor:
   - Spawns claude-loop.sh subprocess
   - Streams events (progress, logs, errors)

4. Progress Reporter:
   - Subscribes to executor events
   - Formats messages
   - Sends to user's channel

5. Quality Gates:
   - Runs after each story
   - Reports results to MetricsLogger

6. Metrics Logger:
   - Records all metrics to disk
   - Feeds data to ImprovementEngine

7. Improvement Engine:
   - Analyzes patterns
   - Generates proposals (if patterns detected)
```

### Parallel Execution Flow

```
1. Multiple users/sessions:
   User A: /autonomous-coding start "Feature A"
   User B: /autonomous-coding start "Feature B"
   User A: /autonomous-coding start "Feature C"

2. Parallel Coordinator:
   - Enqueues tasks (A1, B1, A2)
   - Starts up to maxConcurrent (default: 3)
   - Manages queue: A1 (running), B1 (running), A2 (queued)

3. As tasks complete:
   - A1 completes → A2 starts
   - Resources freed → Next queued task starts
```

## Event System

All components use Node.js EventEmitter for loose coupling:

```typescript
// LoopExecutor events
executor.on('started', (data) => { /* ... */ })
executor.on('progress', (data) => { /* ... */ })
executor.on('story-complete', (data) => { /* ... */ })
executor.on('error', (error) => { /* ... */ })
executor.on('complete', (summary) => { /* ... */ })

// ParallelCoordinator events
coordinator.on('task-started', (data) => { /* ... */ })
coordinator.on('task-progress', (data) => { /* ... */ })
coordinator.on('task-completed', (data) => { /* ... */ })
coordinator.on('task-error', (data) => { /* ... */ })

// ProgressReporter events
reporter.on('message', (formattedMessage) => {
  // Send to user's channel
})
```

## State Management

### Session State

Stored in: `~/.epiloop/sessions/autonomous-coding/<session-id>/`

Contents:
- `prd.json` - Original PRD
- `checkpoint.json` - Current state for resume
- `logs.jsonl` - Structured logs
- `workspace/` - Isolated working directory

### Metrics State

Stored in: `~/.epiloop/metrics/autonomous-coding/`

Contents:
- `<session-id>.json` - Per-session metrics
- `aggregate.json` - Cross-session statistics

### Improvement State

Stored in: `~/.epiloop/improvement/autonomous-coding/`

Contents:
- `improvement-data.json` - Failures, successes, proposals
- `reports/` - Generated reports

## Configuration

Configuration file: `~/.epiloop/config/autonomous-coding.json`

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
  }
}
```

## Error Handling

### Failure Categories

1. **PRD Generation Failures**
   - Invalid feature description
   - Claude API errors
   - Context analysis failures

2. **Execution Failures**
   - Syntax errors in generated code
   - Test failures
   - Quality gate failures
   - Timeout

3. **Resource Failures**
   - Out of memory
   - Disk space exceeded
   - CPU throttling

4. **API Failures**
   - Rate limits
   - Network errors
   - Authentication issues

### Recovery Strategies

- **Checkpoints**: Save state every story for resume
- **Retry Logic**: Exponential backoff for API calls
- **Graceful Degradation**: Continue with warnings if non-critical gates fail
- **Cleanup**: Automatic cleanup of failed sessions

## Performance Considerations

### Scalability

- **Parallel Execution**: Up to N concurrent tasks (configurable)
- **Resource Isolation**: Each session in separate workspace
- **Memory Management**: Streaming logs, paginated metrics queries

### Optimization

- **Smart Batching**: Progress updates batched every 2 seconds
- **Lazy Loading**: Metrics loaded on-demand
- **Incremental Persistence**: Write metrics incrementally, not all at once

## Security

### Workspace Isolation

- Each session has isolated directory
- No cross-session file access
- Resource limits enforced

### API Key Management

- Claude API keys stored in Epiloop credential store
- Never logged or exposed in events

### Code Execution

- Quality gates validate security (npm audit)
- Generated code reviewed before merge

## Testing Strategy

### Unit Tests

- Each component has 10-15 unit tests
- Foundation/Challenge/Reality layers per RG-TDD
- 75%+ code coverage required

### Integration Tests

- End-to-end flows tested
- Mock Claude API responses
- Deterministic test data

### E2E Tests

- Full workflow: command → execution → completion
- Real workspace creation and cleanup
- Event streaming verification

## Deployment

### As Epiloop Extension

1. Install: `npm install @epiloop/claude-loop`
2. Register plugin in Epiloop config
3. Restart Epiloop

### Standalone (Development)

```bash
cd extensions/claude-loop
npm install
npm test
npm run build
```

## Monitoring

### Logs

- Structured JSONL format
- Stored in `~/.epiloop/logs/claude-loop/`
- Rotated daily

### Metrics

- Session success rate
- Average duration per story
- Quality gate pass rates
- Resource usage trends

### Alerts

- Long-running sessions (> 2 hours)
- High failure rates (> 30%)
- Resource exhaustion warnings

## Future Enhancements

1. **Distributed Execution**: Run tasks across multiple machines
2. **GPU Support**: Leverage GPUs for large model inference
3. **Live Collaboration**: Multiple users working on same feature
4. **Visual Studio Code Integration**: Native IDE plugin
5. **Advanced Analytics**: ML-based prediction of success probability
