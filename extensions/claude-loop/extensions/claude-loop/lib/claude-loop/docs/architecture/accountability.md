# Accountability Layer Architecture

**Status**: Implemented (US-ORG-004)
**Version**: 1.0
**Last Updated**: 2026-01-17

## Overview

The Accountability Layer logs all orchestrator decisions with rationale and outcomes for learning and transparency. It tracks decision → outcome correlations to improve future routing decisions through continuous learning.

**Key Capabilities**:
- **Decision Logging**: Complete audit trail of all routing decisions
- **Outcome Tracking**: Links decisions to results (success/failure, time, issues)
- **Learning Algorithm**: Analyzes correlations to suggest confidence adjustments
- **Query Interface**: Fast queries by request_id, time range, outcome type
- **Performance**: <10ms logging overhead, <100ms query time

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    Accountability Layer                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Log Decision                                               │
│     │                                                          │
│     ├─→ Generate Request ID (UUID)                            │
│     ├─→ Capture Timestamp (ISO 8601)                          │
│     ├─→ Store Diagnosis Result                                │
│     ├─→ Store Routing Decisions                               │
│     └─→ Append to orchestrator-decisions.jsonl                │
│                                                                │
│  2. Log Outcome (later)                                        │
│     │                                                          │
│     ├─→ Find Entry by Request ID                              │
│     ├─→ Add Outcome Data (success/failure/partial/cancelled)  │
│     ├─→ Add Time Taken, Issues Found                          │
│     ├─→ Add Tests Passed, Quality Score                       │
│     └─→ Update Entry in Log File                              │
│                                                                │
│  3. Query Interface                                            │
│     │                                                          │
│     ├─→ Filter by Request ID                                  │
│     ├─→ Filter by Time Range (start/end)                      │
│     ├─→ Filter by Outcome Type                                │
│     ├─→ Filter by Has Outcome                                 │
│     └─→ Return Filtered Results                               │
│                                                                │
│  4. Statistics & Analytics                                     │
│     │                                                          │
│     ├─→ Total Decisions                                       │
│     ├─→ Success Rate                                          │
│     ├─→ Average Time                                          │
│     ├─→ Most Common Components                                │
│     └─→ Confidence Accuracy                                   │
│                                                                │
│  5. Learning Algorithm                                         │
│     │                                                          │
│     ├─→ Group Outcomes by Component                           │
│     ├─→ Calculate Success Rate per Component                  │
│     ├─→ Compare to Overall Success Rate                       │
│     └─→ Suggest Confidence Adjustments                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Data Structures

### DecisionLog
```python
@dataclass
class DecisionLog:
    request_id: str              # Unique ID for this decision
    timestamp: str               # ISO 8601 (e.g., "2026-01-17T10:30:00Z")
    user_request: str            # Original user request text
    diagnosis: Dict              # DiagnosisResult as dict
    decisions: Dict              # DecisionResult as dict
    outcome: Optional[Dict]      # Outcome as dict (filled in later)
    logged_at: Optional[str]     # When outcome was logged
```

### Outcome
```python
@dataclass
class Outcome:
    outcome_type: OutcomeType          # SUCCESS, FAILURE, PARTIAL, CANCELLED
    time_taken_seconds: float          # Execution time
    issues_found: List[str]            # List of issues encountered
    tests_passed: Optional[bool]       # Did tests pass?
    quality_score: Optional[float]     # 0.0-1.0
    notes: str                         # Additional notes
```

### OutcomeType Enum
```python
class OutcomeType(str, Enum):
    SUCCESS = "success"      # All operations succeeded
    FAILURE = "failure"      # Operations failed
    PARTIAL = "partial"      # Some operations succeeded, some failed
    CANCELLED = "cancelled"  # User cancelled operation
```

## Log File Format

### JSON Lines Format
**File**: `.claude-loop/orchestrator-decisions.jsonl`

Each line is a complete JSON object representing one `DecisionLog`. This format allows:
- Append-only writes (efficient)
- Line-by-line reading (memory efficient)
- Easy parsing with standard JSON tools

**Example Log Entry (Before Outcome)**:
```json
{
  "request_id": "a1b2c3d4",
  "timestamp": "2026-01-17T10:30:00Z",
  "user_request": "build authentication system with JWT tokens",
  "diagnosis": {
    "complexity": 7,
    "complexity_confidence": 0.9,
    "primary_domain": "security",
    "secondary_domains": ["backend"],
    "domain_confidence": 0.95,
    "operation_type": "creation",
    "operation_confidence": 0.9,
    "risks": [
      {
        "category": "security",
        "level": "HIGH",
        "confidence": 0.9,
        "reasoning": "Authentication system requires security review"
      }
    ],
    "capabilities_needed": ["security-auditor", "brainstorming"],
    "keywords_detected": ["authentication", "JWT", "security"],
    "word_count": 8
  },
  "decisions": {
    "decisions": [
      {
        "component_type": "skill",
        "component_name": "brainstorming",
        "rationale": "High complexity detected",
        "confidence": 0.95,
        "priority": 1,
        "timing": null,
        "rule_applied": "skills.brainstorming.when[0]"
      },
      {
        "component_type": "agent",
        "component_name": "security-auditor",
        "rationale": "HIGH security risk detected",
        "confidence": 0.95,
        "priority": 2,
        "timing": null,
        "rule_applied": "agents.security-auditor.when[1]"
      }
    ],
    "total_confidence": 0.95,
    "execution_order": ["skill:brainstorming", "agent:security-auditor"],
    "human_approval_required": false,
    "approval_reason": ""
  },
  "outcome": null,
  "logged_at": null
}
```

**Example Log Entry (After Outcome)**:
```json
{
  "request_id": "a1b2c3d4",
  "timestamp": "2026-01-17T10:30:00Z",
  "user_request": "build authentication system with JWT tokens",
  "diagnosis": { ... },
  "decisions": { ... },
  "outcome": {
    "outcome_type": "success",
    "time_taken_seconds": 45.3,
    "issues_found": [],
    "tests_passed": true,
    "quality_score": 0.92,
    "notes": "Implementation completed successfully"
  },
  "logged_at": "2026-01-17T10:31:00Z"
}
```

## API Reference

### AccountabilityLogger

```python
class AccountabilityLogger:
    def __init__(self, log_file: str = None):
        """
        Initialize accountability logger.

        Args:
            log_file: Path to log file
                     Default: .claude-loop/orchestrator-decisions.jsonl
        """

    def log_decision(
        self,
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        request_id: str = None
    ) -> str:
        """
        Log a routing decision.

        Args:
            user_request: Original user request text
            diagnosis: DiagnosisResult from situation diagnosis
            decisions: DecisionResult from decision engine
            request_id: Optional custom request ID

        Returns:
            request_id for this decision

        Performance: <10ms
        """

    def log_outcome(
        self,
        request_id: str,
        outcome: Outcome
    ) -> bool:
        """
        Log the outcome of executing routing decisions.

        Args:
            request_id: Request ID from log_decision()
            outcome: Outcome object with results

        Returns:
            True if logged, False if request_id not found

        Performance: <50ms (rewrites log file)
        """

    def query_decisions(
        self,
        request_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        outcome_type: OutcomeType = None,
        has_outcome: bool = None,
        limit: int = 100
    ) -> List[DecisionLog]:
        """
        Query logged decisions with filters.

        Args:
            request_id: Filter by specific request ID
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time
            outcome_type: Filter by outcome type
            has_outcome: Filter by whether outcome logged
            limit: Maximum results (default: 100)

        Returns:
            List of DecisionLog objects

        Performance: <100ms for typical log sizes (<1000 entries)
        """

    def get_decision_statistics(self) -> Dict:
        """
        Get statistics about logged decisions.

        Returns:
            {
                "total_decisions": int,
                "decisions_with_outcomes": int,
                "success_rate": float,  # Percentage
                "avg_time_seconds": float,
                "most_common_components": List[Dict],
                "confidence_accuracy": float  # 0.0-1.0
            }
        """

    def learn_from_outcomes(self) -> Dict[str, float]:
        """
        Suggest confidence adjustments based on outcomes.

        Returns:
            Dict mapping component names to multipliers:
            - 1.0 = no change
            - >1.0 = increase confidence (consistently successful)
            - <1.0 = decrease confidence (frequently fails)

        Algorithm:
            1. Group outcomes by component
            2. Calculate success rate per component
            3. Compare to overall success rate
            4. Suggest adjustments based on deviation
        """
```

## Usage Examples

### Basic Usage Flow

```python
from lib.orchestrator.diagnosis import SituationDiagnosis
from lib.orchestrator.decision_engine import DecisionEngine
from lib.orchestrator.accountability import AccountabilityLogger, Outcome, OutcomeType

# Initialize components
diagnoser = SituationDiagnosis()
engine = DecisionEngine()
logger = AccountabilityLogger()

# User request
user_request = "build authentication system with JWT tokens"

# Step 1: Diagnose situation
diagnosis = diagnoser.diagnose(user_request)

# Step 2: Make routing decisions
decisions = engine.decide(diagnosis)

# Step 3: Log decision (BEFORE execution)
request_id = logger.log_decision(user_request, diagnosis, decisions)

# Step 4: Execute decisions (orchestrator does this)
# ... execute components ...

# Step 5: Log outcome (AFTER execution)
outcome = Outcome(
    outcome_type=OutcomeType.SUCCESS,
    time_taken_seconds=45.3,
    issues_found=[],
    tests_passed=True,
    quality_score=0.92,
    notes="Implementation completed successfully"
)

logger.log_outcome(request_id, outcome)
```

### Query Recent Failures

```python
from datetime import datetime, timedelta

logger = AccountabilityLogger()

# Get failures from last 24 hours
start_time = datetime.utcnow() - timedelta(hours=24)
failures = logger.query_decisions(
    start_time=start_time,
    outcome_type=OutcomeType.FAILURE
)

print(f"Found {len(failures)} failures in last 24 hours")

for entry in failures:
    print(f"\nRequest: {entry.user_request}")
    print(f"Issues: {', '.join(entry.outcome['issues_found'])}")
    print(f"Components: {', '.join(entry.decisions['execution_order'])}")
```

### Get Statistics

```python
logger = AccountabilityLogger()

stats = logger.get_decision_statistics()

print(f"Total Decisions: {stats['total_decisions']}")
print(f"Success Rate: {stats['success_rate']}%")
print(f"Avg Time: {stats['avg_time_seconds']}s")
print(f"\nMost Common Components:")
for item in stats['most_common_components'][:5]:
    print(f"  {item['component']}: {item['count']}")
```

### Learning from Outcomes

```python
logger = AccountabilityLogger()

# Get confidence adjustment recommendations
adjustments = logger.learn_from_outcomes()

print("Confidence Adjustment Recommendations:")
for component, multiplier in sorted(adjustments.items(), key=lambda x: x[1]):
    if multiplier > 1.1:
        print(f"  ↑ {component}: {multiplier:.2f}x (INCREASE)")
    elif multiplier < 0.9:
        print(f"  ↓ {component}: {multiplier:.2f}x (DECREASE)")
    else:
        print(f"  → {component}: {multiplier:.2f}x (OK)")
```

## CLI Interface

The accountability layer includes a CLI for querying and analyzing logs:

### Show Statistics
```bash
python3 lib/orchestrator/accountability.py stats

# Output:
# ============================================================
# DECISION STATISTICS
# ============================================================
#
# Total Decisions: 150
# With Outcomes: 142
# Success Rate: 87.32%
# Avg Time (success): 12.5s
# Confidence Accuracy: 0.73
#
# Most Common Components:
#   skill:brainstorming: 45
#   agent:security-auditor: 32
#   workflow:two-stage-review: 28
#   agent:code-reviewer: 25
#   workflow:tdd-enforcement: 20
```

### Query Decisions
```bash
# Last 24 hours
python3 lib/orchestrator/accountability.py query

# Last 48 hours
python3 lib/orchestrator/accountability.py query --last 48

# Specific request ID
python3 lib/orchestrator/accountability.py query --request-id a1b2c3d4

# Only failures
python3 lib/orchestrator/accountability.py query --outcome failure

# Limit results
python3 lib/orchestrator/accountability.py query --limit 10

# Custom log file
python3 lib/orchestrator/accountability.py query --log-file /path/to/log.jsonl
```

### Learning Recommendations
```bash
python3 lib/orchestrator/accountability.py learn

# Output:
# ============================================================
# CONFIDENCE ADJUSTMENT RECOMMENDATIONS
# ============================================================
#
# agent:debugger: 0.75x (DECREASE)
# agent:git-workflow: 0.92x (OK)
# skill:brainstorming: 1.05x (OK)
# agent:code-reviewer: 1.12x (INCREASE)
# agent:security-auditor: 1.25x (INCREASE)
```

## Learning Algorithm

### How It Works

1. **Group by Component**: Collect all outcomes for each component
2. **Calculate Success Rates**:
   - Overall success rate: `successes / total_decisions`
   - Per-component success rate: `component_successes / component_decisions`
3. **Compare Rates**:
   - If component_rate > overall_rate → component performs better than average
   - If component_rate < overall_rate → component performs worse than average
4. **Calculate Multiplier**: `multiplier = component_rate / overall_rate`
5. **Clamp Range**: Limit multipliers to 0.7-1.3 to avoid drastic changes

### Example Calculation

**Scenario**:
- Overall success rate: 80% (80 successes / 100 decisions)
- security-auditor: 90% success (27 successes / 30 decisions)
- debugger: 60% success (12 successes / 20 decisions)

**Calculations**:
- security-auditor multiplier: `0.90 / 0.80 = 1.125` → Increase confidence
- debugger multiplier: `0.60 / 0.80 = 0.75` → Decrease confidence

**Recommendations**:
- Increase security-auditor confidence by 12.5%
- Decrease debugger confidence by 25%

### Confidence Accuracy Metric

Measures correlation between confidence scores and success rates:

**Algorithm**:
1. **Group by Confidence Bins**:
   - Low: 0.0-0.6
   - Medium: 0.6-0.8
   - High: 0.8-1.0
2. **Calculate Success Rate per Bin**
3. **Check Ordering**: Does success rate increase with confidence?
   - Perfect: high > medium > low → Return average of rates
   - Partial: high > low → Return partial correlation
   - None: No ordering → Return 0.0

**Interpretation**:
- `0.8-1.0`: High correlation (confidence predicts success)
- `0.5-0.8`: Moderate correlation
- `0.0-0.5`: Low/no correlation (confidence doesn't predict success)

## Performance Characteristics

| Operation | Target | Typical | Notes |
|-----------|--------|---------|-------|
| log_decision() | <10ms | 0.05-0.1ms | Append-only write |
| log_outcome() | <50ms | 10-30ms | Rewrites entire file |
| query_decisions() | <100ms | 20-50ms | Linear scan |
| get_statistics() | <100ms | 30-60ms | Full file read |
| learn_from_outcomes() | <200ms | 50-100ms | Analysis of all outcomes |

**Scalability**:
- Log file size: 1000 entries ≈ 1-2 MB
- Query performance degrades linearly with log size
- Recommend log rotation after 10,000 entries

### Log Rotation Strategy (Future Enhancement)

For production deployments with >10,000 entries:
1. Move current log to `orchestrator-decisions-YYYY-MM-DD.jsonl`
2. Start new log file
3. Keep last 7 days of logs
4. Archive older logs to compressed format

## Testing

### Test Coverage

**Test Suite**: `tests/orchestrator/test_accountability.py` (15 test cases)

**Coverage Areas**:
1. **Decision Logging** (Tests 1, 12, 15): Log format, JSON Lines, custom request_id
2. **Outcome Logging** (Tests 2-3): Log outcome, handle nonexistent ID
3. **Query Interface** (Tests 4-8): By ID, time range, outcome type, has_outcome, limit
4. **Statistics** (Test 9): Total, with outcomes, success rate, avg time, common components
5. **Learning** (Test 10): Confidence adjustments based on success/failure patterns
6. **Performance** (Test 11): Logging overhead <10ms verified
7. **Edge Cases** (Tests 13-14): Empty log, confidence accuracy calculation

**Running Tests**:
```bash
python3 tests/orchestrator/test_accountability.py
```

**Expected Output**:
```
============================================================
ACCOUNTABILITY LAYER TEST SUITE
============================================================

✅ Test 1: Log decision and verify format
✅ Test 2: Log outcome for decision
... (13 more tests)

============================================================
RESULTS: 15/15 tests passed
✅ All tests passed!
============================================================
```

## Integration Points

### Input: Decision Engine
```python
# decision_engine.py provides DecisionResult
from lib.orchestrator.decision_engine import DecisionResult

# Accountability layer consumes this along with diagnosis
logger.log_decision(user_request, diagnosis, decisions)
```

### Output: Transparency Layer (US-ORG-005)
```python
# Transparency layer uses logged decisions for explanations
recent_decisions = logger.query_decisions(
    start_time=datetime.utcnow() - timedelta(hours=1),
    limit=10
)

# Show user their recent decisions and outcomes
for entry in recent_decisions:
    explain_decision(entry)
```

### Output: Continuous Learning
```python
# Periodically update confidence scores based on outcomes
adjustments = logger.learn_from_outcomes()

# Apply adjustments to orchestrator-rules.yaml (manual review recommended)
for component, multiplier in adjustments.items():
    if multiplier < 0.85 or multiplier > 1.15:
        print(f"Consider adjusting {component} confidence by {multiplier:.2f}x")
```

## Troubleshooting

### Log File Not Found
**Issue**: `FileNotFoundError: .claude-loop/orchestrator-decisions.jsonl`

**Solution**: The directory is created automatically on first `log_decision()`. Ensure write permissions.

### Slow Queries
**Issue**: Queries take >100ms

**Cause**: Log file has >1000 entries

**Solutions**:
1. Reduce query scope with time range filters
2. Implement log rotation (future enhancement)
3. Use external database for production deployments

### Outcome Not Logged
**Issue**: `log_outcome()` returns `False`

**Cause**: Request ID doesn't exist in log

**Solutions**:
1. Verify request_id is correct
2. Check that `log_decision()` was called first
3. Ensure log file wasn't rotated/deleted between calls

### Learning Returns Empty Dict
**Issue**: `learn_from_outcomes()` returns `{}`

**Cause**: Insufficient data (<3 outcomes per component)

**Solution**: Log more decisions with outcomes. Need at least 3 samples per component for learning.

## Future Enhancements

### Planned (US-ORG-005 through US-ORG-011)
- **Transparency Integration**: Use logs for detailed decision explanations
- **Human-in-the-Loop Tracking**: Log user overrides and learn from them
- **Benchmark Integration**: Use logs for regression detection
- **Automatic Confidence Tuning**: Apply learning adjustments automatically

### Under Consideration
- **Database Backend**: SQLite or PostgreSQL for production scale
- **Log Rotation**: Automatic rotation and archiving
- **Real-time Analytics**: Dashboard for live monitoring
- **A/B Testing**: Compare different routing strategies
- **Anomaly Detection**: Detect unusual patterns in decisions/outcomes

## References

- **Situation Diagnosis Engine**: `docs/architecture/situation-diagnosis.md`
- **Decision Engine**: `docs/architecture/decision-engine.md`
- **Transparency Layer**: `docs/architecture/transparency-layer.md` (US-ORG-005, TODO)
- **Orchestrator Overview**: `docs/analysis/orchestration-audit-2026-01-16.md`
- **PRD**: `prds/drafts/intelligent-orchestration-system/prd.json`
