# Hook System Guide

## Overview

The Hook System provides lifecycle hooks that allow you to customize claude-loop's behavior without modifying core code. Hooks enable:

- **Extensibility**: Add custom functionality at key points in execution
- **Integration**: Connect with external services (Slack, monitoring, etc.)
- **Automation**: Auto-format code, run custom validators, etc.
- **Observability**: Log events, track metrics, send notifications

**Inspired by**: [clawdbot's plugin architecture](https://github.com/cyanheads/clawdbot)

## Quick Start

### Basic Hook

```python
from lib.hooks import HookType, HookContext, register_hook

def my_hook(context: HookContext) -> HookContext:
    """A simple hook that logs story starts."""
    print(f"Story {context.story_id} is starting!")
    return context

# Register the hook
register_hook(HookType.BEFORE_STORY_START, my_hook, priority=50)
```

### Loading Hooks

```bash
# In your script or worker
python3 -c "import hooks.examples.notify_slack"

# Or set as module import
export CLAUDE_LOOP_HOOKS="hooks.examples.notify_slack,hooks.examples.auto_format"
```

## Lifecycle Hooks

### Available Hook Points

| Hook Type | When It Runs | Use Cases |
|-----------|--------------|-----------|
| **BEFORE_STORY_START** | Before executing a story | Notifications, setup, validation |
| **AFTER_STORY_COMPLETE** | After story completes successfully | Cleanup, formatting, notifications |
| **BEFORE_TOOL_CALL** | Before any tool execution | Logging, rate limiting, caching |
| **AFTER_TOOL_CALL** | After tool execution | Result processing, sanitization |
| **ON_ERROR** | When an error occurs | Error reporting, rollback, recovery |
| **ON_SESSION_END** | When session ends | Cleanup, final reports, metrics |

### Hook Context

Every hook receives a `HookContext` object:

```python
@dataclass
class HookContext:
    story_id: Optional[str] = None          # Current story ID (e.g., "US-001")
    prd_data: Optional[Dict] = None         # Full PRD data
    session_id: Optional[str] = None        # Session identifier
    iteration: int = 0                      # Current iteration number
    tool_name: Optional[str] = None         # Tool being called (for tool hooks)
    tool_args: Optional[Dict] = None        # Tool arguments
    tool_result: Optional[Any] = None       # Tool result (after execution)
    error: Optional[Exception] = None       # Error object (for error hooks)
    metadata: Dict = field(default_factory=dict)  # Custom data
```

## Hook Registration

### Priority System

Hooks run in **priority order** (higher number = runs first):

```python
# High priority (runs first)
register_hook(HookType.BEFORE_STORY_START, critical_setup, priority=100)

# Medium priority (runs second)
register_hook(HookType.BEFORE_STORY_START, normal_setup, priority=50)

# Low priority (runs last)
register_hook(HookType.BEFORE_STORY_START, optional_setup, priority=10)
```

**Priority Guidelines**:
- **100+**: Critical system hooks
- **75-99**: Important pre-processing
- **50-74**: Normal priority (default)
- **25-49**: Post-processing
- **1-24**: Optional/cosmetic hooks

### Registration Methods

#### 1. Global Registry (Simple)

```python
from lib.hooks import register_hook, HookType

def my_hook(context):
    return context

register_hook(HookType.BEFORE_STORY_START, my_hook)
```

#### 2. Custom Registry (Advanced)

```python
from lib.hooks import HookRegistry, HookType

registry = HookRegistry()
registry.register(HookType.BEFORE_STORY_START, my_hook, priority=75)

# Run hooks manually
context = registry.run_hooks(HookType.BEFORE_STORY_START, context)
```

#### 3. Decorator Pattern (Future)

```python
# Future enhancement
@hook(HookType.BEFORE_STORY_START, priority=50)
def my_hook(context):
    return context
```

## Writing Hooks

### Basic Hook Template

```python
def my_hook_name(context: HookContext) -> HookContext:
    """
    Brief description of what this hook does.

    Hook: BEFORE_STORY_START
    Priority: 50
    """
    try:
        # Your hook logic here
        print(f"Processing story: {context.story_id}")

        # Optionally modify context
        context.update(processed=True)

        # Always return context
        return context

    except Exception as e:
        # Error isolation: log but don't crash
        print(f"Hook failed: {e}")
        return context
```

### Modifying Context

Hooks can modify context for downstream hooks:

```python
def enrich_context(context: HookContext) -> HookContext:
    """Add metadata to context."""
    context.update(
        start_time=time.time(),
        custom_field="value"
    )
    return context

def use_enriched_context(context: HookContext) -> HookContext:
    """Use metadata added by previous hook."""
    start_time = context.metadata.get('start_time')
    if start_time:
        duration = time.time() - start_time
        print(f"Elapsed: {duration:.2f}s")
    return context

# Register in order
register_hook(HookType.BEFORE_STORY_START, enrich_context, priority=100)
register_hook(HookType.AFTER_STORY_COMPLETE, use_enriched_context, priority=50)
```

### Async Hooks

```python
async def async_hook(context: HookContext) -> HookContext:
    """Async hook for I/O operations."""
    await asyncio.sleep(0.1)  # Async operation
    print(f"Async processing for {context.story_id}")
    return context

# Register as async
register_hook(HookType.BEFORE_STORY_START, async_hook, async_hook=True)

# Run async hooks
context = await run_hooks_async(HookType.BEFORE_STORY_START, context)
```

## Example Hooks

### 1. Slack Notifications

**File**: `hooks/examples/notify-slack.py`

```python
def notify_story_start(context: HookContext) -> HookContext:
    """Send Slack notification when story starts."""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')

    requests.post(webhook_url, json={
        "text": f":rocket: Story Started: {context.story_id}"
    })

    return context

register_hook(HookType.BEFORE_STORY_START, notify_story_start)
```

**Configuration**:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
python3 -c "import hooks.examples.notify_slack"
```

### 2. Auto-Format Code

**File**: `hooks/examples/auto-format.py`

```python
def auto_format_after_story(context: HookContext) -> HookContext:
    """Format code with black after story completion."""
    subprocess.run(['black', '.', '--quiet'])
    print("Code formatted with black")
    return context

register_hook(HookType.AFTER_STORY_COMPLETE, auto_format_after_story, priority=25)
```

### 3. Error Reporting

```python
def report_errors(context: HookContext) -> HookContext:
    """Send error reports to monitoring service."""
    if not context.error:
        return context

    # Send to error tracking service
    sentry_sdk.capture_exception(context.error)

    # Log locally
    with open('errors.log', 'a') as f:
        f.write(f"{context.story_id}: {context.error}\n")

    return context

register_hook(HookType.ON_ERROR, report_errors, priority=75)
```

### 4. Metrics Collection

```python
def collect_metrics(context: HookContext) -> HookContext:
    """Collect performance metrics."""
    # Track story completion
    metrics_db.increment('stories_completed')

    # Track iteration count
    metrics_db.histogram('iterations_per_story', context.iteration)

    return context

register_hook(HookType.AFTER_STORY_COMPLETE, collect_metrics)
```

### 5. Custom Validation

```python
def validate_story(context: HookContext) -> HookContext:
    """Validate story before starting."""
    if not context.story_id:
        raise ValueError("Story ID is required")

    if context.prd_data:
        # Check required fields
        required = ['project', 'description']
        for field in required:
            if field not in context.prd_data:
                raise ValueError(f"Missing required field: {field}")

    return context

register_hook(HookType.BEFORE_STORY_START, validate_story, priority=100)
```

## Error Handling

### Error Isolation

**Hooks are error-isolated**: If one hook fails, others still run.

```python
def failing_hook(context):
    raise Exception("This hook fails!")

def working_hook(context):
    print("This hook still runs")
    return context

# Both registered
register_hook(HookType.BEFORE_STORY_START, failing_hook, priority=100)
register_hook(HookType.BEFORE_STORY_START, working_hook, priority=50)

# failing_hook will log error, but working_hook still executes
```

### Best Practices

```python
def safe_hook(context: HookContext) -> HookContext:
    """Hook with proper error handling."""
    try:
        # Risky operation
        result = external_api_call()

        # Update context
        context.update(api_result=result)

    except Exception as e:
        # Log error
        logger.error(f"Hook failed: {e}", exc_info=True)

        # Don't re-raise - error isolation
        # Optionally update context with error info
        context.update(hook_error=str(e))

    # Always return context
    return context
```

## Advanced Patterns

### Conditional Hooks

```python
def conditional_hook(context: HookContext) -> HookContext:
    """Only run hook for specific stories."""

    # Skip if not matching story
    if not context.story_id or not context.story_id.startswith("US-CRITICAL"):
        return context

    # Run special processing for critical stories
    send_high_priority_notification(context)

    return context
```

### Hook Chains

```python
def hook_chain_start(context: HookContext) -> HookContext:
    """Start of hook chain."""
    context.update(chain_data=[])
    return context

def hook_chain_middle(context: HookContext) -> HookContext:
    """Middle of hook chain."""
    data = context.metadata.get('chain_data', [])
    data.append('processed')
    context.update(chain_data=data)
    return context

def hook_chain_end(context: HookContext) -> HookContext:
    """End of hook chain."""
    data = context.metadata.get('chain_data', [])
    print(f"Chain completed with {len(data)} steps")
    return context

# Register in order
register_hook(HookType.BEFORE_STORY_START, hook_chain_start, priority=100)
register_hook(HookType.BEFORE_STORY_START, hook_chain_middle, priority=75)
register_hook(HookType.BEFORE_STORY_START, hook_chain_end, priority=50)
```

### Dynamic Hook Loading

```python
def load_hooks_from_config(config_file: str):
    """Load hooks dynamically from configuration."""
    import importlib

    with open(config_file) as f:
        config = yaml.safe_load(f)

    for hook_config in config.get('hooks', []):
        module_name = hook_config['module']
        hook_name = hook_config['function']
        hook_type = HookType(hook_config['type'])
        priority = hook_config.get('priority', 50)

        # Import module
        module = importlib.import_module(module_name)

        # Get hook function
        hook_fn = getattr(module, hook_name)

        # Register
        register_hook(hook_type, hook_fn, priority=priority)
```

## Testing Hooks

### Unit Testing

```python
def test_my_hook():
    """Test hook in isolation."""
    from lib.hooks import HookContext
    from hooks.examples.notify_slack import notify_story_start

    # Create test context
    context = HookContext(
        story_id="US-TEST",
        prd_data={"project": "test"}
    )

    # Run hook
    result = notify_story_start(context)

    # Verify
    assert result.story_id == "US-TEST"
```

### Integration Testing

```python
def test_hook_registration():
    """Test hook registration and execution."""
    from lib.hooks import HookRegistry, HookType

    registry = HookRegistry()
    call_count = {'count': 0}

    def test_hook(context):
        call_count['count'] += 1
        return context

    # Register
    registry.register(HookType.BEFORE_STORY_START, test_hook)

    # Run
    context = HookContext()
    registry.run_hooks(HookType.BEFORE_STORY_START, context)

    # Verify
    assert call_count['count'] == 1
```

## Performance Considerations

### Keep Hooks Fast

```python
# BAD: Slow synchronous I/O
def slow_hook(context):
    time.sleep(5)  # Blocks execution
    return context

# GOOD: Async I/O
async def fast_hook(context):
    await async_api_call()  # Non-blocking
    return context
```

### Avoid Heavy Processing

```python
# BAD: Heavy computation in hook
def heavy_hook(context):
    result = run_expensive_analysis()  # Slows down execution
    return context

# GOOD: Offload to background
def lightweight_hook(context):
    queue.put({'story_id': context.story_id})  # Queue for background
    return context
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_lookup(key: str):
    """Cache expensive lookups."""
    return database.query(key)

def cached_hook(context: HookContext) -> HookContext:
    """Hook with caching."""
    result = expensive_lookup(context.story_id)
    context.update(cached_result=result)
    return context
```

## Debugging Hooks

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('hooks')

def debug_hook(context: HookContext) -> HookContext:
    """Hook with debug logging."""
    logger.debug(f"Hook called for story: {context.story_id}")
    logger.debug(f"Context: {context.__dict__}")
    return context
```

### Hook Tracing

```python
def trace_hook(context: HookContext) -> HookContext:
    """Trace hook execution."""
    import traceback

    print(f"\n=== Hook Trace: {context.story_id} ===")
    print(f"Call stack:")
    traceback.print_stack()

    return context
```

## Best Practices

### 1. Always Return Context

```python
# GOOD
def good_hook(context):
    # ... processing ...
    return context

# BAD
def bad_hook(context):
    # ... processing ...
    # Missing return!
```

### 2. Use Type Hints

```python
def typed_hook(context: HookContext) -> HookContext:
    """Type hints improve IDE support and catch errors."""
    return context
```

### 3. Document Your Hooks

```python
def documented_hook(context: HookContext) -> HookContext:
    """
    Send notifications to team chat.

    Hook: BEFORE_STORY_START
    Priority: 50
    Dependencies: SLACK_WEBHOOK_URL environment variable

    Args:
        context: Hook context with story information

    Returns:
        Unmodified context
    """
    return context
```

### 4. Handle Missing Data Gracefully

```python
def robust_hook(context: HookContext) -> HookContext:
    """Handle missing data gracefully."""

    # Use get() with defaults
    story_id = context.story_id or "UNKNOWN"

    # Check before accessing
    if context.prd_data:
        project = context.prd_data.get('project', 'N/A')
    else:
        project = 'N/A'

    return context
```

### 5. Don't Modify Core State

```python
# BAD: Modifying global state
def bad_hook(context):
    global_config['modified'] = True  # Side effects!
    return context

# GOOD: Use context metadata
def good_hook(context):
    context.update(modified=True)  # Contained
    return context
```

## Troubleshooting

### Hook Not Running

1. **Check Registration**:
   ```python
   from lib.hooks import get_registry
   registry = get_registry()
   print(f"Hooks registered: {registry.count()}")
   print(registry.get_hooks(HookType.BEFORE_STORY_START))
   ```

2. **Check Import**:
   - Ensure hook module is imported
   - Check for import errors

3. **Check Priority**:
   - Higher priority runs first
   - Verify execution order

### Hook Fails Silently

Hooks are error-isolated. Check logs:

```python
import logging
logging.basicConfig(level=logging.ERROR)
# Re-run to see error messages
```

### Performance Issues

1. **Profile Hooks**:
   ```python
   import time

   def profiled_hook(context):
       start = time.time()
       # ... hook logic ...
       duration = time.time() - start
       print(f"Hook took {duration:.3f}s")
       return context
   ```

2. **Use Async for I/O**:
   - Network calls
   - File operations
   - Database queries

## References

- **Implementation**: [`lib/hooks.py`](../../lib/hooks.py)
- **Tests**: [`tests/test_hooks.py`](../../tests/test_hooks.py)
- **Examples**: [`hooks/examples/`](../../hooks/examples/)
- **Clawdbot Inspiration**: [Plugin architecture](https://github.com/cyanheads/clawdbot)

## Future Enhancements

Planned improvements:

1. **Decorator Syntax**: `@hook(HookType.BEFORE_STORY_START)`
2. **Hook Marketplace**: Community-contributed hooks
3. **Hook Dependencies**: Declare dependencies between hooks
4. **Conditional Registration**: `register_if(condition, hook)`
5. **Hook Metrics**: Track execution time, failure rate
6. **Visual Hook Graph**: See hook execution flow
