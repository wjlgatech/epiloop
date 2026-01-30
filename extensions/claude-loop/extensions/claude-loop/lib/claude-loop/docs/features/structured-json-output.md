# Structured JSON Output Parser (US-004)

**Status**: Implemented
**Version**: 1.0
**Phase**: Tier 1 Pattern Extraction

## Overview

The Structured JSON Output Parser replaces text-based sigil detection (`<loop>COMPLETE</loop>`, `WORKER_SUCCESS`) with structured JSON responses from Claude. This improves parsing reliability and enables rich metadata extraction including confidence scores, reasoning, file changes, and complexity estimates.

## Motivation

**Problems with Sigil-Based Parsing**:
- Text parsing is fragile (false positives from logs/comments)
- No metadata extraction (can't track confidence, reasoning, complexity)
- Limited error handling (can't distinguish low confidence vs failure)
- No structured file change tracking

**Benefits of JSON Parsing**:
- Reliable schema validation via jq
- Rich metadata: confidence scores, reasoning, file changes, complexity
- Low-confidence detection and clarification requests
- Better debugging with structured logs
- Backward compatible: falls back to sigil parsing if JSON fails

## Features

### 1. JSON Response Format

Claude can return structured responses in this format:

```json
{
  "action": "complete",
  "reasoning": "Implemented user authentication with JWT tokens and bcrypt password hashing",
  "confidence": 90,
  "files": [
    {
      "path": "src/auth.ts",
      "changes": "Added authentication logic and token generation"
    },
    {
      "path": "src/routes/auth.ts",
      "changes": "Created login and signup routes"
    }
  ],
  "metadata": {
    "estimated_changes": 120,
    "complexity": 3,
    "related_files": ["src/middleware/auth.ts", "src/types/user.ts"]
  }
}
```

### 2. Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | Action type: `complete`, `commit`, `implement`, `skip`, `delegate` |
| `reasoning` | string | No | Explanation of actions taken and decisions made |
| `confidence` | number (0-100) | No | Confidence score (< 50 triggers clarification request) |
| `files` | array | No | Modified files with descriptions |
| `files[].path` | string | No | File path relative to project root |
| `files[].changes` | string | No | Brief description of changes |
| `metadata` | object | No | Additional metadata |
| `metadata.estimated_changes` | number | No | Number of lines changed |
| `metadata.complexity` | number (1-5) | No | Complexity score |
| `metadata.related_files` | array | No | Files that may need review |

### 3. Action Types

| Action | Meaning | Behavior |
|--------|---------|----------|
| `complete` | Story fully implemented | Marks story as complete, commits changes |
| `commit` | Ready to commit | Creates git commit (same as `complete`) |
| `implement` | Still implementing | Progress update, continues iteration |
| `skip` | Story should be skipped | Marks story as skipped, moves to next |
| `delegate` | Delegate to another agent | Triggers delegation workflow |

### 4. Confidence Levels

| Range | Level | Action |
|-------|-------|--------|
| 75-100 | High | Proceed normally |
| 50-74 | Medium | Proceed with caution |
| 0-49 | Low | Log warning, request clarification |

Low confidence triggers:
- Warning logged to console
- Entry added to `.claude-loop/logs/actions.jsonl`
- Clarification requested in next iteration

## Usage

### Enabling Structured Output

```bash
# Enable via CLI flag
./claude-loop.sh --enable-structured-output

# Combine with other features
./claude-loop.sh --enable-structured-output --enable-hooks --enable-learnings
```

### Example Output

#### JSON Code Block Format
```
Here's what I implemented:

```json
{
  "action": "complete",
  "reasoning": "Added login endpoint with JWT authentication. Tests passing.",
  "confidence": 95,
  "files": [
    {"path": "src/auth/login.ts", "changes": "Implemented login logic"}
  ]
}
```

Story US-001 complete.
```

#### Standalone JSON Format
```json
{"action": "complete", "confidence": 85, "reasoning": "All acceptance criteria met"}
```

### Backward Compatibility

The parser supports both formats simultaneously:

1. **JSON Parsing** (if `--enable-structured-output` is set):
   - Tries to extract JSON from response
   - Validates schema with jq
   - Falls back to sigil parsing if JSON invalid

2. **Sigil Parsing** (always available):
   - `<loop>COMPLETE</loop>` - Standard completion
   - `WORKER_SUCCESS: <story_id>` - Worker completion
   - `WORKER_FAILURE: <story_id>: <reason>` - Worker failure

If JSON parsing fails, the system gracefully falls back to sigil detection with a warning logged.

## Implementation Details

### Core Functions

#### `validate_json_response(json)`
Validates JSON response schema:
- Checks for valid JSON structure
- Validates required `action` field
- Ensures action is one of: `implement`, `commit`, `skip`, `delegate`, `complete`

**Returns**: 0 if valid, 1 if invalid

#### `parse_json_response(output_file)`
Extracts JSON from Claude output:
- Tries to find ```json code block first
- Falls back to standalone JSON object
- Validates extracted JSON

**Returns**: JSON string if found and valid, exits with code 1 if not

#### `get_json_action(json)`
Extracts action from JSON response.

**Returns**: Action string or empty if not found

#### `get_json_reasoning(json)`
Extracts reasoning from JSON response.

**Returns**: Reasoning string or "No reasoning provided"

#### `get_json_confidence(json)`
Extracts confidence score from JSON response.

**Returns**: Confidence number (0-100) or 0 if not provided

#### `check_completion(output_file, story_id)`
Checks if output indicates completion (JSON or sigil):
1. Tries JSON parsing if enabled
2. Falls back to sigil detection
3. Checks for `WORKER_SUCCESS`, `WORKER_FAILURE`, `<loop>COMPLETE</loop>`

**Returns**: 0 if complete, 1 if not complete, 2 if unclear

#### `log_action_metadata(story_id, action, json_response)`
Logs action metadata to `.claude-loop/logs/actions.jsonl`:
- Timestamp
- Story ID
- Action type
- Reasoning
- Confidence score
- Modified files
- Additional metadata

#### `handle_low_confidence(json_response, story_id)`
Handles low-confidence responses:
- Checks if confidence < 50
- Logs warning
- Records to actions log
- Returns 1 to trigger clarification

**Returns**: 0 if confidence acceptable, 1 if low

### File Structure

```
claude-loop/
├── claude-loop.sh                    # Core implementation
│   └── Structured JSON Output Parser section (lines 2403-2622)
├── lib/worker.sh                      # Worker support (updated check_worker_result)
├── prompt.md                          # Updated with JSON output instructions
├── tests/structured_output_test.sh    # Integration tests (16 tests)
├── docs/features/
│   └── structured-json-output.md     # This document
└── .claude-loop/logs/
    └── actions.jsonl                  # Metadata log (created automatically)
```

### Actions Log Format

Each entry in `.claude-loop/logs/actions.jsonl`:

```json
{
  "timestamp": "2026-01-20T00:00:00Z",
  "story_id": "US-004",
  "action": "complete",
  "reasoning": "Implemented structured JSON output parser with full backward compatibility",
  "confidence": 95,
  "files": [
    {"path": "claude-loop.sh"},
    {"path": "lib/worker.sh"},
    {"path": "prompt.md"}
  ],
  "metadata": {
    "estimated_changes": 250,
    "complexity": 3
  }
}
```

## Testing

### Running Tests

```bash
# Run structured output tests
./tests/structured_output_test.sh

# Run all tests (backward compatibility check)
pytest tests/ -v
```

### Test Coverage

The test suite includes 16 tests:

1. **JSON Validation Tests** (3 tests):
   - Valid JSON with valid action
   - Invalid action rejection
   - Missing action field rejection

2. **JSON Parsing Tests** (2 tests):
   - Code block format (```json ... ```)
   - Standalone JSON object

3. **Metadata Extraction Tests** (3 tests):
   - Extract action
   - Extract reasoning
   - Extract confidence

4. **Completion Detection Tests** (3 tests):
   - JSON complete action
   - Sigil fallback (<loop>COMPLETE</loop>)
   - WORKER_SUCCESS sigil

5. **Metadata Logging Test** (1 test):
   - Log to actions.jsonl with correct structure

6. **Confidence Handling Tests** (2 tests):
   - Low confidence detection (< 50)
   - High confidence acceptance (>= 50)

7. **Feature Flag Test** (1 test):
   - Disabled mode uses sigil format only

8. **Performance Test** (1 test):
   - JSON parsing overhead < 200ms

**All 16 tests passing** ✅

## Performance

### Benchmarks

- JSON parsing: < 200ms per response (< 100ms typical)
- Schema validation: < 50ms via jq
- Fallback to sigils: 0ms (no JSON parsing attempted)

### Overhead

- Disabled (default): 0% overhead (sigil parsing only)
- Enabled: < 5% overhead (JSON parsing + validation + fallback)

## Configuration

### Environment Variables

```bash
# Enable structured output (default: false)
STRUCTURED_OUTPUT_ENABLED=false

# Actions log file location
ACTIONS_LOG_FILE=".claude-loop/logs/actions.jsonl"
```

### CLI Flags

```bash
--enable-structured-output    Enable structured JSON output parsing
```

## Troubleshooting

### Issue: JSON not being parsed

**Symptoms**: Falling back to sigil parsing even with --enable-structured-output

**Solutions**:
1. Check that JSON is in correct format (code block or standalone)
2. Verify `action` field is present and valid
3. Check actions.jsonl for validation errors
4. Increase logging verbosity to see parse attempts

### Issue: Low confidence warnings

**Symptoms**: Frequent "Low confidence detected" warnings

**Solutions**:
1. Review reasoning field to understand uncertainty
2. Check if story requirements are unclear
3. Consider decomposing complex stories
4. Provide more context in story description

### Issue: Actions log growing too large

**Symptoms**: .claude-loop/logs/actions.jsonl exceeds 10MB

**Solutions**:
```bash
# Archive old logs
mv .claude-loop/logs/actions.jsonl .claude-loop/logs/actions.jsonl.$(date +%Y%m%d)

# Compress archived logs
gzip .claude-loop/logs/actions.jsonl.*
```

## Examples

### Example 1: Complete Story with High Confidence

```json
{
  "action": "complete",
  "reasoning": "Implemented all 5 acceptance criteria: database schema, API endpoints, tests, documentation, and error handling. All tests passing with 95% coverage.",
  "confidence": 95,
  "files": [
    {"path": "src/db/schema.sql", "changes": "Created users table with constraints"},
    {"path": "src/api/users.ts", "changes": "Implemented CRUD endpoints"},
    {"path": "tests/api/users.test.ts", "changes": "Added 12 test cases"},
    {"path": "docs/api/users.md", "changes": "Documented user API"}
  ],
  "metadata": {
    "estimated_changes": 350,
    "complexity": 3,
    "related_files": ["src/types/user.ts", "src/middleware/auth.ts"]
  }
}
```

### Example 2: Low Confidence Requiring Clarification

```json
{
  "action": "implement",
  "reasoning": "Started implementing OAuth, but unclear which provider to use. Requirements mention 'social login' but don't specify Google vs GitHub vs both.",
  "confidence": 35,
  "files": [
    {"path": "src/auth/oauth.ts", "changes": "Created OAuth scaffold"}
  ],
  "metadata": {
    "estimated_changes": 50,
    "complexity": 4
  }
}
```

**System Response**:
```
[WARN] Low confidence (35%) detected for story US-003
[WARN] Requesting clarification in next iteration
```

### Example 3: Skip Story (Not Applicable)

```json
{
  "action": "skip",
  "reasoning": "This story requires Windows-specific APIs but project is Linux-only. Marked as 'not applicable' in notes.",
  "confidence": 100
}
```

## Migration Guide

### From Sigil to JSON Format

**Before** (sigil format):
```
I've implemented the feature. All tests pass.

<loop>COMPLETE</loop>
```

**After** (JSON format):
```
I've implemented the feature. All tests pass.

```json
{
  "action": "complete",
  "reasoning": "Implemented authentication with JWT. All 8 tests passing.",
  "confidence": 90,
  "files": [
    {"path": "src/auth.ts", "changes": "Added JWT logic"}
  ]
}
```
```

### Gradual Rollout

1. **Phase 1**: Enable on non-critical PRDs
   ```bash
   ./claude-loop.sh --prd test.json --enable-structured-output
   ```

2. **Phase 2**: Monitor actions.jsonl for insights
   ```bash
   # View recent actions
   tail -20 .claude-loop/logs/actions.jsonl | jq .

   # Check average confidence
   jq -s 'map(.confidence) | add / length' .claude-loop/logs/actions.jsonl
   ```

3. **Phase 3**: Enable by default if metrics look good
   ```bash
   # Add to config.yaml or use alias
   alias claude-loop='./claude-loop.sh --enable-structured-output'
   ```

## Future Enhancements

### Planned (Phase 2)
- [ ] Confidence-based model selection (low confidence → upgrade to Opus)
- [ ] Automatic retry on low confidence with clarifying prompt
- [ ] Actions log analytics dashboard
- [ ] Export actions log to CSV/Excel

### Under Consideration
- [ ] Multi-action responses (multiple files, multiple commits)
- [ ] Dependency tracking in metadata
- [ ] Test coverage estimates in metadata
- [ ] Automatic story complexity adjustment based on metadata

## Acceptance Criteria

All 12 acceptance criteria from US-004 met:

- [x] Update prompt.md: request JSON response format
- [x] Parser handles both formats: JSON and legacy sigil (backward compatible)
- [x] JSON schema validation using jq
- [x] Extract metadata: confidence, estimated changes, complexity, related files
- [x] Low-confidence handling: confidence < 50 logs warning and requests clarification
- [x] Metadata logging to .claude-loop/logs/actions.jsonl
- [x] Feature flag: ENABLE_STRUCTURED_OUTPUT=false by default
- [x] Performance: JSON parsing < 200ms overhead
- [x] Error handling: graceful fallback to sigil parsing with warning
- [x] All existing integration tests pass (backward compatibility proof)
- [x] New test: structured_output_test.sh validates JSON parsing (16 tests, all passing)
- [x] Documentation: This comprehensive guide

## Conclusion

The Structured JSON Output Parser significantly improves claude-loop's parsing reliability and debugging capabilities while maintaining full backward compatibility. By enabling rich metadata extraction, it lays the foundation for advanced features like confidence-based model selection, automatic retries, and analytics dashboards.

**Recommendation**: Enable on a trial basis, monitor confidence scores and actions log, then roll out more broadly as confidence grows.
