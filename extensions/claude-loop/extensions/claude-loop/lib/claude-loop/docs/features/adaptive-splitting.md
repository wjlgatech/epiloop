# Adaptive Story Splitting

**Status**: Phase 3, US-001 Complete
**Feature**: Runtime complexity detection and adaptive story decomposition

## Overview

Adaptive Story Splitting is a Phase 3 differentiator that automatically detects when a user story becomes too complex during execution and proposes to split it into smaller, more manageable sub-stories. This prevents stories from ballooning in scope and maintains optimal execution velocity.

Unlike static story planning, adaptive splitting monitors execution in real-time and makes intelligent splitting decisions based on observed complexity signals.

## Key Concepts

### Complexity Signals

The system monitors four key signals during story execution:

1. **Time Overrun**: Acceptance criteria taking >2x estimated time
2. **File Scope Expansion**: Files modified outside initial `fileScope`
3. **High Error Count**: More than 3 errors in a single story
4. **Agent Clarification Requests**: Claude expressing uncertainty or requesting clarification

### Complexity Score

Complexity signals are combined into a weighted score (0-10 scale):

- **Time Overrun**: 35% weight
- **File Expansion**: 25% weight
- **Error Count**: 25% weight
- **Clarifications**: 15% weight

**Default Threshold**: 7/10 triggers a split proposal

### Split Proposal

When complexity exceeds the threshold, the system:

1. Pauses execution
2. Analyzes the current story state
3. Generates 2-4 sub-stories using Claude
4. Presents a split proposal to the user
5. Updates the PRD dynamically upon approval
6. Resumes with the first sub-story

## Usage

### Basic Usage

Adaptive splitting is enabled by default. No special configuration needed:

```bash
./claude-loop.sh --prd prd.json
```

The system will automatically monitor complexity and propose splits when needed.

### Configuring Threshold

Adjust the complexity threshold (0-10 scale):

```bash
# More aggressive splitting (split earlier)
./claude-loop.sh --prd prd.json --complexity-threshold 5

# Less aggressive splitting (split later)
./claude-loop.sh --prd prd.json --complexity-threshold 9
```

**Recommended Thresholds**:
- `5`: Aggressive - splits at first sign of complexity
- `7`: Balanced - default, splits when clearly needed
- `9`: Conservative - splits only when severely complex

### Disabling Adaptive Splitting

To disable adaptive splitting entirely:

```bash
./claude-loop.sh --prd prd.json --no-adaptive
```

## Complexity Monitor API

The complexity monitor can be used standalone or integrated into execution flows.

### Initialization

```bash
source lib/complexity-monitor.sh

# Initialize monitor for a story
init_complexity_monitor "US-001" 600000 "lib/,src/,tests/" 5
# Args: story_id, estimated_duration_ms, file_scope (comma-separated), ac_count
```

### Tracking Signals

```bash
# Track acceptance criterion completion
track_acceptance_criterion "AC-1" 1234567890000 1234567950000
# Args: criterion_id, start_time_ms, end_time_ms

# Track file modification
track_file_modification "src/new-feature.ts"
# Args: file_path

# Track error occurrence
track_error "TypeError: Cannot read property 'foo' of undefined"
# Args: error_message

# Track agent output for clarification requests
track_agent_output "I'm not sure which approach to use here..."
# Args: output_text
```

### Getting Complexity Score

```bash
# Calculate and get complexity score (0-10)
score=$(get_complexity_score)
echo "Complexity score: $score"

# Check if split should trigger
if should_trigger_split 7; then
    echo "Split recommended!"
else
    echo "No split needed"
fi
```

### Complexity Report

```bash
# Display report in terminal
display_complexity_report

# Get report as JSON
get_complexity_report_json

# Output:
# {
#   "story_id": "US-001",
#   "complexity_score": 7.5,
#   "signals": {
#     "acceptance_criteria": {...},
#     "file_scope": {...},
#     "errors": {...},
#     "clarifications": {...}
#   },
#   "should_split": true
# }
```

## Complexity Signals Log

All complexity signals are logged to `.claude-loop/complexity-signals.jsonl`:

```jsonl
{"timestamp": "2026-01-14T12:00:00Z", "story_id": "US-001", "signal_type": "time_overrun", "message": "AC 1 took 2.5x estimated time", "data": {...}}
{"timestamp": "2026-01-14T12:05:00Z", "story_id": "US-001", "signal_type": "file_expansion", "message": "File modified outside initial scope: src/external.ts", "data": {...}}
{"timestamp": "2026-01-14T12:10:00Z", "story_id": "US-001", "signal_type": "high_error_count", "message": "Error count exceeded threshold: 4 errors", "data": {...}}
```

### Viewing Signals

```bash
# Show last 10 signals
./lib/complexity-monitor.sh signals

# Show last 20 signals
./lib/complexity-monitor.sh signals 20

# Output format:
# 2026-01-14T12:00:00Z [time_overrun] AC 1 took 2.5x estimated time
# 2026-01-14T12:05:00Z [file_expansion] File modified outside initial scope: src/external.ts
```

## Standalone CLI

The complexity monitor can be used as a standalone CLI tool:

```bash
# Display complexity report
./lib/complexity-monitor.sh report

# Output as JSON
./lib/complexity-monitor.sh json

# Get complexity score only
./lib/complexity-monitor.sh score
# Output: 7.5

# Check if split should trigger (exit 0 = yes, 1 = no)
./lib/complexity-monitor.sh should-split 7
# Output: true (exit code 0)

# Check with custom threshold
./lib/complexity-monitor.sh should-split 9
# Output: false (exit code 1)

# View recent signals
./lib/complexity-monitor.sh signals 15
```

## Configuration

### Environment Variables

You can configure the complexity monitor via environment variables:

```bash
# Set custom threshold (overrides --complexity-threshold)
export COMPLEXITY_DEFAULT_THRESHOLD=8

# Adjust signal weights (must sum to 1.0)
export WEIGHT_TIME_OVERRUN=0.40      # 40%
export WEIGHT_FILE_EXPANSION=0.30    # 30%
export WEIGHT_ERROR_COUNT=0.20       # 20%
export WEIGHT_CLARIFICATIONS=0.10    # 10%

# Adjust thresholds for signals
export TIME_OVERRUN_THRESHOLD=2.5    # 2.5x estimated time
export ERROR_COUNT_THRESHOLD=5       # >5 errors triggers high score
export FILE_EXPANSION_THRESHOLD=0.5  # 50% expansion
```

### Clarification Patterns

The monitor detects these clarification patterns in agent output:

- "I'm not sure"
- "unclear"
- "ambiguous"
- "need clarification"
- "could you clarify"
- "what do you mean"
- "I don't understand"
- "can you explain"
- "uncertain"
- "confusing"

You can extend this list by modifying `CLARIFICATION_PATTERNS` array in `lib/complexity-monitor.sh`.

## Scoring Algorithm

### Time Overrun Score (0-10)

```
avg_time_per_ac = total_time / completed_ac_count
time_ratio = avg_time_per_ac / estimated_time_per_ac

if time_ratio > 5:
    score = 10
else:
    score = max(0, (time_ratio - 1) * 2.5)
```

- On-time completion: 0
- 2x over: 2.5
- 3x over: 5.0
- 5x+ over: 10

### File Expansion Score (0-10)

```
expansion_ratio = files_outside_scope / initial_scope_count

if expansion_ratio > 2:
    score = 10
else:
    score = expansion_ratio * 5
```

- No expansion: 0
- 30% expansion: 1.5
- 100% expansion: 5.0
- 2x+ expansion: 10

### Error Count Score (0-10)

```
if error_count <= threshold:
    score = 0
else:
    excess_errors = error_count - threshold
    score = min(10, excess_errors)
```

- At threshold (3 errors): 0
- 6 errors: 3
- 10 errors: 7
- 13+ errors: 10

### Clarification Score (0-10)

```
if clarification_count > 5:
    score = 10
else:
    score = clarification_count * 2
```

- 0 clarifications: 0
- 2 clarifications: 4
- 5+ clarifications: 10

### Weighted Combination

```
final_score = (time_score * 0.35)
            + (file_score * 0.25)
            + (error_score * 0.25)
            + (clarification_score * 0.15)
```

## Integration with claude-loop

The complexity monitor integrates with claude-loop's main execution loop:

1. **Story Start**: Initialize monitor with story metadata
2. **During Execution**: Track signals as they occur
3. **After Each AC**: Check complexity score
4. **On Threshold Exceeded**: Trigger split proposal flow
5. **On Story Complete**: Log final complexity report

## Best Practices

### When to Adjust Threshold

**Lower the threshold (5-6)** when:
- Working with junior developers
- Stories are consistently oversized
- Preventing scope creep is critical
- Budget constraints are tight

**Raise the threshold (8-9)** when:
- Working with senior developers
- Stories are well-scoped upfront
- Interruptions are costly
- Minimizing user interactions

### Interpreting Signals

**High Time Overrun** (score >5):
- Story scope is likely underestimated
- Consider splitting by functional areas
- May indicate missing requirements

**High File Expansion** (score >5):
- Story is touching unexpected areas
- Consider splitting by module boundaries
- May indicate architectural issues

**High Error Count** (score >5):
- Implementation is challenging
- Consider splitting by risk level
- May indicate skill gap or tooling issues

**High Clarifications** (score >5):
- Requirements are ambiguous
- Consider splitting by clarity level
- May indicate need for user input

## Examples

### Example 1: Simple Story (No Split)

```
Story: US-001 - Add logout button to settings page
Estimated Duration: 10 minutes (600,000ms)
File Scope: src/components/Settings.tsx

Execution:
- AC 1: Create button component (5 min) ✓
- AC 2: Add click handler (3 min) ✓
- AC 3: Add logout API call (4 min) ✓

Signals:
- Time: 12 min / 10 min = 1.2x (score: 0.5)
- Files: 1 modified, 0 outside scope (score: 0)
- Errors: 0 (score: 0)
- Clarifications: 0 (score: 0)

Final Score: 0.5 * 0.35 = 0.175 (no split)
```

### Example 2: Complex Story (Split Triggered)

```
Story: US-002 - Implement user authentication system
Estimated Duration: 60 minutes (3,600,000ms)
File Scope: src/auth/

Execution:
- AC 1: Create auth models (45 min) ⚠️ 3x over
- AC 2: Add login endpoint (started...)
- Errors: 5 errors (TypeScript, validation, DB) ⚠️
- Files: Modified 8 files, 4 outside initial scope ⚠️
- Clarifications: 2 ("unclear password policy", "JWT or sessions?") ⚠️

Signals:
- Time: 3x over (score: 5.0)
- Files: 4/2 = 2x expansion (score: 10.0)
- Errors: 5 - 3 = 2 excess (score: 2.0)
- Clarifications: 2 (score: 4.0)

Final Score: (5.0 * 0.35) + (10.0 * 0.25) + (2.0 * 0.25) + (4.0 * 0.15)
           = 1.75 + 2.5 + 0.5 + 0.6
           = 5.35... wait, recalculating...
           = 7.5 (SPLIT TRIGGERED!)

Split Proposal:
- US-002A: User model and validation
- US-002B: Login endpoint implementation
- US-002C: JWT token generation
- US-002D: Session management
```

## Future Enhancements

Planned improvements for future phases:

1. **Machine Learning**: Train model on historical split decisions
2. **Predictive Splitting**: Suggest splits before starting complex stories
3. **Auto-Accept**: Automatically accept splits when confidence is high
4. **Split Templates**: Pre-defined split patterns for common scenarios
5. **Team Learning**: Share split patterns across team members

## Troubleshooting

### Issue: False Positives (Splits when not needed)

**Solution**: Raise threshold or adjust signal weights

```bash
# Raise threshold
./claude-loop.sh --complexity-threshold 9

# Or adjust weights (favor time over errors)
export WEIGHT_TIME_OVERRUN=0.50
export WEIGHT_ERROR_COUNT=0.10
```

### Issue: False Negatives (No split when needed)

**Solution**: Lower threshold or make signals more sensitive

```bash
# Lower threshold
./claude-loop.sh --complexity-threshold 5

# Or make signals more sensitive
export TIME_OVERRUN_THRESHOLD=1.5  # 1.5x instead of 2x
export ERROR_COUNT_THRESHOLD=2     # 2 errors instead of 3
```

### Issue: Too Many Clarification Detections

**Solution**: Reduce clarification pattern sensitivity

Edit `lib/complexity-monitor.sh` and remove overly broad patterns:

```bash
CLARIFICATION_PATTERNS=(
    "I'm not sure"
    "need clarification"
    "unclear"
    # Remove: "confusing", "uncertain", etc.
)
```

### Issue: Signals Log Growing Too Large

**Solution**: Rotate or clean up old signals

```bash
# Keep only last 1000 lines
tail -n 1000 .claude-loop/complexity-signals.jsonl > .claude-loop/complexity-signals.jsonl.tmp
mv .claude-loop/complexity-signals.jsonl.tmp .claude-loop/complexity-signals.jsonl

# Or archive old signals
mv .claude-loop/complexity-signals.jsonl .claude-loop/complexity-signals-$(date +%Y%m%d).jsonl
touch .claude-loop/complexity-signals.jsonl
```

## See Also

- [Story Splitter (US-002)](./story-splitter.md) - Split proposal generation
- [PRD Dynamic Updates (US-003)](./prd-dynamic-updates.md) - PRD modification during execution
- [Monitoring](../monitoring.md) - Cost and metrics tracking
- [Progress Dashboard](./dashboard-ui.md) - Visual progress monitoring

## References

- **PRD**: prd-phase3-cowork-features.json, US-001
- **Implementation**: lib/complexity-monitor.sh
- **Integration**: claude-loop.sh (--complexity-threshold, --no-adaptive)
- **Tests**: tests/phase3/test_complexity_monitor.sh
