# Model Failover and API Key Rotation

## Overview

The Model Failover system provides automatic retry and fallback capabilities when API calls fail due to rate limits, provider outages, or other transient errors. It supports:

- **Multi-Provider Fallback**: anthropic → openai → google → deepseek
- **API Key Rotation**: Automatically cycle through multiple keys on rate limits
- **Exponential Backoff**: Intelligent retry delays (1s, 2s, 4s, etc.)
- **Error Classification**: Different strategies for different error types

This feature is inspired by clawdbot's multi-provider failover system.

## Motivation

API failures can disrupt autonomous execution:

- **Rate Limits**: Hitting usage caps on a single API key
- **Provider Outages**: Temporary unavailability of a service
- **Quota Exhaustion**: Running out of credits mid-execution
- **Network Issues**: Transient connectivity problems

Without failover, these issues require manual intervention. With failover, execution continues seamlessly.

## How It Works

### 1. Error Classification

The system classifies errors into categories that determine the failover strategy:

| Error Type | HTTP Codes | Keywords | Strategy |
|------------|------------|----------|----------|
| **RATE_LIMIT** | 429 | "rate limit" | Rotate API key |
| **AUTHENTICATION** | 401, 403 | "unauthorized", "invalid api key" | Rotate key, then switch provider |
| **SERVER_ERROR** | 500, 502, 503, 504 | "server error", "internal error" | Retry with backoff |
| **OVERLOADED** | 529 | "overloaded", "capacity" | Switch provider |
| **TIMEOUT** | - | "timeout", "timed out" | Retry with backoff |
| **CONTEXT_LENGTH** | - | "context length", "too many tokens" | Fatal (requires different approach) |

### 2. Failover Chain

```
Attempt 1: Anthropic (Key 1) - Rate Limit (429)
Attempt 2: Anthropic (Key 2) - Success ✓
```

```
Attempt 1: Anthropic (Key 1) - Overloaded (529)
Attempt 2: OpenAI (Key 1) - Timeout
Attempt 3: OpenAI (Key 1) - Success ✓  [after 2s backoff]
```

```
Attempt 1: Anthropic - Auth Error (401)
Attempt 2: OpenAI - Server Error (500)
Attempt 3: Google - Success ✓  [after 4s backoff]
```

### 3. Exponential Backoff

Delays between retries grow exponentially:

- Attempt 1 → 2: 1 second
- Attempt 2 → 3: 2 seconds
- Attempt 3 → 4: 4 seconds
- Attempt 4 → 5: 8 seconds
- Max delay: 60 seconds

## Configuration

### YAML Configuration

Add to `config.yaml`:

```yaml
failover:
  enabled: true
  max_total_attempts: 12
  backoff_base: 1.0
  backoff_max: 60.0

  providers:
    - name: anthropic
      api_keys:
        - ${ANTHROPIC_API_KEY}
        - ${ANTHROPIC_API_KEY_2}  # For rotation
      models:
        - claude-3-5-sonnet-20241022
        - claude-3-5-haiku-20241022

    - name: openai
      api_keys:
        - ${OPENAI_API_KEY}
      models:
        - gpt-4o
        - gpt-4o-mini
```

### Python API

```python
from lib.model_failover import ModelFailover, ProviderConfig, Provider

# Configure providers
providers = [
    ProviderConfig(
        provider=Provider.ANTHROPIC,
        api_keys=["key1", "key2"],
        models=["claude-3-5-sonnet-20241022"]
    ),
    ProviderConfig(
        provider=Provider.OPENAI,
        api_keys=["key3"],
        models=["gpt-4o"]
    )
]

# Create failover manager
failover = ModelFailover(
    providers=providers,
    max_total_attempts=12,
    backoff_base=1.0,
    backoff_max=60.0
)

# Execute with automatic failover
def make_api_call(api_key, model, provider_config):
    # Your API call logic here
    response = client.messages.create(
        model=model,
        api_key=api_key,
        messages=[...]
    )
    return response

result = failover.execute_with_failover(make_api_call)
```

## Use Cases

### Scenario 1: Rate Limit Recovery

```python
# Anthropic rate limit → rotate to backup key
providers = [
    ProviderConfig(
        Provider.ANTHROPIC,
        api_keys=["primary_key", "backup_key"]
    )
]

failover = ModelFailover(providers=providers)
result = failover.execute_with_failover(api_call)

# Log output:
# Attempt 1: anthropic/claude-3-5-sonnet (key 1) - Rate limit
# Rotated to API key 2/2
# Attempt 2: anthropic/claude-3-5-sonnet (key 2) - Success
```

### Scenario 2: Provider Outage

```python
# Anthropic down → switch to OpenAI
providers = [
    ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
    ProviderConfig(Provider.OPENAI, api_keys=["key2"])
]

failover = ModelFailover(providers=providers)
result = failover.execute_with_failover(api_call)

# Log output:
# Attempt 1: anthropic/claude-3-5-sonnet (key 1) - Server error (503)
# Backing off for 1.0s
# Attempt 2: anthropic/claude-3-5-sonnet (key 1) - Server error (503)
# Switched to provider: openai
# Attempt 3: openai/gpt-4o (key 1) - Success
```

### Scenario 3: Complete Fallback Chain

```python
# All providers tried until success
providers = [
    ProviderConfig(Provider.ANTHROPIC, api_keys=["key1"]),
    ProviderConfig(Provider.OPENAI, api_keys=["key2"]),
    ProviderConfig(Provider.GOOGLE, api_keys=["key3"]),
    ProviderConfig(Provider.DEEPSEEK, api_keys=["key4"])
]

failover = ModelFailover(providers=providers)
result = failover.execute_with_failover(api_call)

# Tries: Anthropic → OpenAI → Google → DeepSeek
```

## Error Handling

### Recoverable Errors

These errors trigger retry/failover:

- Rate limits (429)
- Server errors (500, 502, 503, 504)
- Timeouts
- Provider overload (529)

### Fatal Errors

These errors stop execution immediately:

- **Invalid API Key**: No point retrying with same key (rotates first)
- **Context Length**: Requires reducing input size, not retrying
- **Unknown Errors**: After exhausting all attempts

### Failure Summary

When all attempts fail, get a detailed summary:

```python
try:
    result = failover.execute_with_failover(api_call)
except RuntimeError as e:
    failover.log_failure_summary()
    # Output:
    # === Failover Attempt Summary ===
    #   #1: anthropic/claude-3-5-sonnet (key 1) - rate_limit
    #   #2: anthropic/claude-3-5-sonnet (key 2) - rate_limit
    #   #3: openai/gpt-4o (key 1) - timeout
    #   #4: openai/gpt-4o (key 1) - server_error
```

## Integration Points

### Worker Execution

Currently, the failover system is implemented as a library. Future integration points:

1. **lib/worker.sh**: Wrap Claude CLI calls with failover
2. **API Client**: Create python wrapper for claude CLI with failover
3. **Autonomous Loop**: Integrate at main execution level

Example future integration:

```bash
# worker.sh with failover
execute_claude_with_failover() {
    python3 lib/api_wrapper.py \
        --model sonnet \
        --failover-enabled \
        --prompt "$prompt"
}
```

## Testing

Comprehensive test suite covers:

```bash
# Run all tests (33 test cases)
python3 -m pytest tests/test_model_failover.py -v

# Key test categories:
# - Error classification (9 tests)
# - Retry decisions (6 tests)
# - Backoff calculation (3 tests)
# - Provider configuration (5 tests)
# - Failover execution (7 tests)
# - Configuration loading (3 tests)
```

## Performance Characteristics

- **Overhead**: ~1ms per attempt (negligible)
- **Memory**: <1MB (state tracking)
- **Latency**: Dominated by backoff delays
  - Fast path (success on attempt 1): 0ms overhead
  - Typical retry (3 attempts): ~7s total (1s + 2s + 4s backoff)
  - Full chain (12 attempts): ~60s max

## Best Practices

### 1. Configure Multiple Keys

```yaml
providers:
  - name: anthropic
    api_keys:
      - ${ANTHROPIC_API_KEY_PRIMARY}
      - ${ANTHROPIC_API_KEY_BACKUP}
      - ${ANTHROPIC_API_KEY_TEAM}
```

**Why**: Rate limits are per-key. Multiple keys = higher throughput.

### 2. Order Providers by Cost

```yaml
providers:
  - anthropic  # Primary (best quality)
  - deepseek   # Fallback (budget-friendly)
  - openai     # Final fallback
```

**Why**: Use expensive providers first, cheap ones as backup.

### 3. Set Appropriate Timeouts

```yaml
providers:
  - name: anthropic
    timeout: 60  # Complex requests need time
  - name: deepseek
    timeout: 30  # Simpler provider, shorter timeout
```

**Why**: Prevent hanging on slow providers.

### 4. Monitor Failover Metrics

```python
# After execution, check attempts
print(f"Total attempts: {len(failover.attempts)}")
for attempt in failover.attempts:
    print(f"  {attempt.provider.value}: {attempt.error_type.value}")
```

**Why**: Identify patterns (frequent rate limits = need more keys).

### 5. Reset State Between Tasks

```python
# Reset after each independent task
failover.reset()
result = failover.execute_with_failover(next_api_call)
```

**Why**: Each task should start fresh (provider index = 0).

## Comparison with Clawdbot

| Feature | claude-loop | clawdbot |
|---------|-------------|----------|
| Error Classification | 7 types | 5 types |
| Backoff Strategy | Exponential | Exponential |
| API Key Rotation | Yes | Yes |
| Provider Switching | Yes (4 providers) | Yes (3 providers) |
| Configuration | YAML + Python API | Config file |
| Default Max Attempts | 12 | 10 |
| Failure Summary | Detailed logs | Basic logs |

## Future Enhancements

Potential improvements:

1. **Smart Provider Selection**: Choose provider based on task type (coding → DeepSeek, reasoning → Claude)
2. **Cost Optimization**: Track cost per provider, prefer cheaper when quality is similar
3. **Latency Tracking**: Prefer faster providers when time-sensitive
4. **Circuit Breaker**: Temporarily skip providers with repeated failures
5. **Metrics Dashboard**: Visualize failover patterns over time

## Troubleshooting

### Issue: Too Many Retries

```python
# Reduce max attempts
failover = ModelFailover(max_total_attempts=6)
```

### Issue: Backoff Too Slow

```python
# Reduce backoff delays
failover = ModelFailover(backoff_base=0.5, backoff_max=30)
```

### Issue: Provider Not Tried

```python
# Check provider order in config
# Ensure API keys are set
config, api_key, model = failover.get_current_config()
print(f"Current: {config.provider.value}")
```

### Issue: All Attempts Failing

```python
# Review failure summary
failover.log_failure_summary()
# Check: Are all API keys valid?
# Check: Network connectivity?
# Check: Provider status pages?
```

## References

- **Implementation**: [`lib/model_failover.py`](../../lib/model_failover.py)
- **Tests**: [`tests/test_model_failover.py`](../../tests/test_model_failover.py)
- **Configuration**: [`config.yaml.example`](../../config.yaml.example) (failover section)
- **Clawdbot Inspiration**: [Multi-provider failover in clawdbot](https://github.com/cyanheads/clawdbot)
