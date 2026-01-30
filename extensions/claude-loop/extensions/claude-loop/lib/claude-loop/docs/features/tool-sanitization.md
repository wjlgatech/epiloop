# Tool Result Sanitization

## Overview

The Tool Result Sanitization feature prevents context overflow by automatically truncating large outputs from Claude's tool executions while preserving important information at both the beginning and end of the content.

This feature is inspired by [clawdbot's tool result sanitization approach](https://github.com/cyanheads/clawdbot) and helps maintain stable, predictable token usage during long-running autonomous sessions.

## Motivation

Without sanitization, large tool outputs can cause several problems:

- **Context Overflow**: Large file reads or command outputs can exhaust the available token budget
- **Performance Degradation**: Massive outputs slow down API requests and increase costs
- **Lost Context**: When the context fills up, important conversation history may be truncated
- **Unpredictable Behavior**: Token limits can be hit unexpectedly, causing execution failures

## How It Works

The sanitizer intercepts Claude's output and applies intelligent truncation:

1. **Size Check**: If output is under the threshold (default: 30,000 chars), it passes through unchanged
2. **Smart Truncation**: For large outputs, preserves:
   - **Head**: First ~90% of allowed characters (important context)
   - **Tail**: Last ~10% of allowed characters (final results/conclusions)
   - **Marker**: Clear indication of truncation with character count
3. **Special Handling**:
   - Binary data: Shows size only (e.g., `[Binary data: 3.24 KB]`)
   - None values: Converts to `"null"`
   - Nested structures: Recursively sanitizes dictionaries and lists

## Configuration

### Environment Variables

```bash
# Enable/disable sanitization (default: true)
export SANITIZE_OUTPUT=true

# Set maximum characters before truncation (default: 30000)
export SANITIZE_MAX_CHARS=30000

# Run worker with sanitization disabled
SANITIZE_OUTPUT=false ./lib/worker.sh US-001
```

### Python API

```python
from lib.tool_sanitizer import ToolSanitizer, sanitize_tool_result

# Quick usage
sanitized = sanitize_tool_result(large_text, max_chars=8000)

# Custom configuration
sanitizer = ToolSanitizer(
    max_chars=10000,  # Total max characters
    head_chars=9000,  # Characters from beginning
    tail_chars=1000   # Characters from end
)

result = sanitizer.sanitize(large_output)

# Sanitize nested dictionaries
tool_response = {
    "output": "..." * 10000,
    "metadata": {"logs": "..." * 5000}
}
sanitized_dict = sanitizer.sanitize_dict(tool_response)
```

### CLI Usage

```bash
# Sanitize a file
python3 lib/tool_sanitizer.py large_file.txt 8000

# Pipe content
cat large_output.log | python3 lib/tool_sanitizer.py - 5000

# Custom max_chars (default: 8000)
echo "..." | python3 lib/tool_sanitizer.py - 10000
```

## Output Format

When content is truncated, the output looks like:

```
[First 7500 characters of content preserved here...]

[... truncated 15,234 chars ...]

[Last 500 characters of content preserved here...]
```

The truncation marker shows:
- Exact number of characters removed
- Formatted with commas for readability
- Surrounded by newlines for visual separation

## Use Cases

### Preventing Context Overflow

```bash
# Large git diff that could overflow context
git diff main > diff.txt
sanitized=$(python3 lib/tool_sanitizer.py diff.txt 8000)
```

### Processing Large Files

```python
from lib.tool_sanitizer import sanitize_tool_result

# Read large log file safely
with open("app.log", "r") as f:
    content = f.read()

# Sanitize before sending to Claude
sanitized = sanitize_tool_result(content, max_chars=10000)
```

### Nested Data Structures

```python
from lib.tool_sanitizer import ToolSanitizer

sanitizer = ToolSanitizer(max_chars=5000)

response = {
    "stdout": "..." * 20000,
    "stderr": "..." * 10000,
    "files": [
        {"path": "a.txt", "content": "..." * 8000},
        {"path": "b.txt", "content": "..." * 6000},
    ]
}

# Recursively sanitize all values
sanitized = sanitizer.sanitize_dict(response)
```

## Integration Points

### Worker Execution (Automatic)

The sanitizer is automatically integrated into `lib/worker.sh`:

- Applied to Claude's output after JSON extraction
- Configurable via `SANITIZE_OUTPUT` and `SANITIZE_MAX_CHARS` environment variables
- Defaults to 30,000 characters (conservative for long outputs)
- Can be disabled if needed

### Custom Tool Integration

You can integrate the sanitizer into custom tools:

```python
from lib.tool_sanitizer import sanitize_tool_result

def read_large_file(path):
    with open(path, "r") as f:
        content = f.read()
    # Sanitize before returning
    return sanitize_tool_result(content, max_chars=8000)
```

## Performance Characteristics

- **Processing Speed**: ~1-2ms for 10,000 character strings
- **Memory**: Minimal overhead (creates one truncated copy)
- **UTF-8 Safe**: Handles Unicode characters correctly
- **Binary Detection**: Fast path for binary data (no processing)

## Testing

The sanitizer includes comprehensive test coverage:

```bash
# Run all tests (18 test cases, 100% coverage of core logic)
python3 -m pytest tests/test_tool_sanitizer.py -v

# Run with coverage report
python3 -m pytest tests/test_tool_sanitizer.py --cov=lib.tool_sanitizer --cov-report=term-missing
```

## Comparison with Clawdbot

| Feature | claude-loop | clawdbot |
|---------|-------------|----------|
| Truncation Strategy | Head + Tail | Head + Tail |
| Default Max Chars | 30,000 (worker), 8,000 (library) | 8,000 |
| Binary Handling | Size display | Size display |
| Nested Structures | Recursive sanitization | Recursive sanitization |
| Configuration | Environment variables + API | Config file |
| Integration | Worker output + standalone | Tool execution pipeline |

## Best Practices

1. **Choose Appropriate Thresholds**:
   - Use 8,000 chars for individual tool results
   - Use 30,000 chars for aggregated outputs
   - Adjust based on your context budget

2. **Preserve Important Content**:
   - Default 90/10 head/tail split works well for most cases
   - For error logs, consider 50/50 split (head + tail equally important)
   - For code files, keep more of the head (structure definitions)

3. **Monitor Truncation**:
   - Log when truncation occurs
   - Review truncated content periodically
   - Adjust thresholds if important data is being cut

4. **Disable When Necessary**:
   - Small, controlled executions don't need sanitization
   - Debugging sessions may need full output
   - Use `SANITIZE_OUTPUT=false` for these cases

## Future Enhancements

Potential improvements from clawdbot analysis:

- **Content-Aware Truncation**: Preserve code blocks, JSON structures, and markdown formatting
- **Smart Sampling**: Instead of pure head/tail, sample important sections throughout
- **Compression**: Apply lightweight compression before truncation
- **Metrics**: Track truncation statistics (frequency, size savings, impact)

## Troubleshooting

### Output Still Too Large

```bash
# Reduce max_chars threshold
export SANITIZE_MAX_CHARS=15000
```

### Important Content Being Truncated

```python
# Adjust head/tail ratio
sanitizer = ToolSanitizer(
    max_chars=8000,
    head_chars=6000,  # 75% head
    tail_chars=2000   # 25% tail
)
```

### Sanitization Not Applied

```bash
# Check that tool_sanitizer.py is accessible
ls -la lib/tool_sanitizer.py

# Verify environment variable
echo $SANITIZE_OUTPUT  # Should be "true"

# Check worker logs for warnings
tail -f .claude-loop/workers/*/logs/error.log
```

## References

- **Implementation**: [`lib/tool_sanitizer.py`](../../lib/tool_sanitizer.py)
- **Tests**: [`tests/test_tool_sanitizer.py`](../../tests/test_tool_sanitizer.py)
- **Integration**: [`lib/worker.sh`](../../lib/worker.sh) (lines 81-93, 404-428)
- **Clawdbot Inspiration**: [Tool result sanitization in clawdbot](https://github.com/cyanheads/clawdbot)
