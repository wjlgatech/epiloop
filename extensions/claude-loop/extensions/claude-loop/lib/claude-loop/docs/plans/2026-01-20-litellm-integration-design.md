# LiteLLM Integration Design

**Date**: 2026-01-20
**Story**: US-006 - Integrate Multi-Provider LLM (LiteLLM)
**Status**: Design Phase

## Overview

Integrate LiteLLM library into claude-loop's existing multi-provider architecture to enable access to 100+ LLM providers while maintaining the optimized direct provider implementations for core use cases.

### Current State

Claude-loop already has a sophisticated multi-provider LLM system (Phase 0.9):
- Abstract provider interface (`lib/llm_provider.py`)
- Direct provider implementations (`lib/providers/openai_provider.py`, `gemini_provider.py`, `deepseek_provider.py`)
- Provider configuration management (`lib/llm_config.py`)
- Cost tracking (`lib/cost_tracker.py`)
- Provider health monitoring (`lib/provider_health.py`)

### Integration Strategy

**Hybrid Approach**: Add LiteLLM as an additional provider option rather than replacing existing implementations.

**Rationale**:
- Existing direct providers are optimized for performance and control
- LiteLLM provides access to 100+ additional providers
- Users can choose based on needs (speed vs breadth)
- Gradual migration path if needed
- Maintains backward compatibility

## Architecture

### Component Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Provider Selection Layer                  │
│                  (lib/provider_selector.py)                  │
│                                                              │
│  - Complexity-based routing                                 │
│  - Cost optimization                                         │
│  - Fallback chain management                                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼─────┐       ┌───────▼───────┐    ┌──────▼──────┐
   │  Direct  │       │   LiteLLM     │    │  Claude     │
   │ Providers│       │   Provider    │    │   Code CLI  │
   │          │       │               │    │  (fallback) │
   │ - OpenAI │       │ - 100+ models │    └─────────────┘
   │ - Gemini │       │ - Unified API │
   │ -DeepSeek│       │ - Auto-retry  │
   └──────────┘       └───────────────┘
```

### Provider Selection Logic

**Complexity-Based Routing**:
```python
def select_provider(complexity: int,
                   requires_vision: bool = False,
                   requires_tools: bool = False,
                   preferred_provider: Optional[str] = None) -> str:
    """
    Select cheapest capable provider based on task requirements

    Complexity thresholds:
    - complexity < 3: cheap models (Haiku, GPT-4o-mini, Gemini Flash)
    - complexity 3-5: medium models (Sonnet, GPT-4o, Gemini Pro)
    - complexity > 5: powerful models (Opus, O1, Gemini Thinking)

    Filter by capabilities:
    - vision required → filter to vision-capable models
    - tools required → filter to tool-capable models

    Select cheapest from filtered list based on cost_per_1k
    """
```

**Fallback Chain**:
```python
# Primary provider selection
primary = select_provider(complexity, requires_vision, requires_tools)

# Fallback chain (configurable)
fallback_chain = [
    primary,
    "claude-sonnet",  # reliable fallback
    "openai-gpt-4o",  # secondary fallback
    "claude-code-cli" # ultimate fallback (always works)
]

# Try each in order until one succeeds
for provider in fallback_chain:
    try:
        return call_provider(provider, messages)
    except (RateLimitError, TimeoutError) as e:
        log_provider_failure(provider, e)
        continue

raise ProviderError("All providers in fallback chain failed")
```

### Cost Tracking

**Provider Usage Log**: `.claude-loop/logs/provider_usage.jsonl`

```json
{
  "timestamp": "2026-01-20T10:00:00Z",
  "story_id": "US-006",
  "iteration": 3,
  "provider": "litellm",
  "model": "gpt-4o-mini",
  "complexity": 2,
  "input_tokens": 1500,
  "output_tokens": 800,
  "cost_usd": 0.0045,
  "latency_ms": 1250,
  "success": true,
  "fallback_used": false
}
```

**Cost Comparison Report**:
```bash
$ ./claude-loop.sh --cost-report

Cost Analysis Report
====================
Period: Last 7 days
Total Requests: 245

Provider Usage:
- litellm/gpt-4o-mini: 120 requests, $12.50 (51%)
- claude-sonnet: 80 requests, $45.00 (33%)
- gemini-2.0-flash: 40 requests, $2.80 (16%)
- fallbacks triggered: 5 requests (2%)

Cost Comparison:
- Actual total: $60.30
- If all Opus: $180.00
- Savings: $119.70 (66% reduction)

Avg latency: 1.8s
Success rate: 98%
```

## Implementation Plan

### Phase 1: LiteLLM Provider Implementation (6 hours)

1. **Install LiteLLM** (`requirements.txt`)
   ```
   litellm>=1.54.0
   ```

2. **Create LiteLLM Provider** (`lib/providers/litellm_provider.py`)
   - Inherit from `LLMProvider` base class
   - Implement `complete()` and `complete_with_vision()` methods
   - Wrap litellm.completion() with error handling
   - Convert responses to standard `LLMResponse` format
   - Register with `ProviderFactory`

3. **Update Provider Config** (`lib/llm_config.py`)
   ```yaml
   litellm:
     name: litellm
     enabled: false  # disabled by default
     timeout: 120
     max_tokens: 4096
     default_model: gpt-4o-mini
     available_models: []  # auto-detected from litellm
     input_cost_per_1k: 0.15  # gpt-4o-mini
     output_cost_per_1k: 0.60
     extra_settings:
       fallback_models: [gpt-4o, claude-sonnet-4-5]
   ```

### Phase 2: Provider Selection Logic (5 hours)

1. **Create Provider Selector** (`lib/provider_selector.py`)
   - `select_provider(complexity, capabilities)` function
   - Complexity-based model selection
   - Capability filtering (vision, tools, JSON mode)
   - Cost-based optimization

2. **Add Fallback Chain** (`lib/provider_selector.py`)
   - Configurable fallback order
   - Retry logic with exponential backoff
   - Provider failure tracking
   - Automatic fallback on rate limits/timeouts

3. **Integration Point** (modify `claude-loop.sh`)
   ```bash
   # Before calling LLM
   if [[ "$ENABLE_MULTI_PROVIDER" == "true" ]]; then
       SELECTED_PROVIDER=$(python3 lib/provider_selector.py select \
           --complexity "$COMPLEXITY" \
           --requires-vision "$REQUIRES_VISION" \
           --requires-tools "$REQUIRES_TOOLS")
   else
       SELECTED_PROVIDER="claude"  # default
   fi
   ```

### Phase 3: Cost Tracking & Reporting (4 hours)

1. **Extend Cost Tracking** (`lib/cost_tracker.py`)
   - Add `provider` and `model` fields
   - Track `fallback_used` flag
   - Calculate per-provider totals

2. **Provider Usage Logger**
   - Append to `.claude-loop/logs/provider_usage.jsonl`
   - Include: timestamp, story, provider, model, tokens, cost, success

3. **Cost Report Generator** (`lib/cost_report.py`)
   - Aggregate usage by provider
   - Calculate savings vs baseline (all-Opus)
   - Show success rates and latencies
   - CLI: `./claude-loop.sh --cost-report [--days N]`

### Phase 4: Feature Flag & Configuration (2 hours)

1. **Feature Flag** (`claude-loop.sh`)
   ```bash
   ENABLE_MULTI_PROVIDER="${ENABLE_MULTI_PROVIDER:-false}"

   # CLI flag
   --enable-multi-provider)
       ENABLE_MULTI_PROVIDER=true
       ;;
   ```

2. **Provider Config** (`lib/llm_providers.yaml`)
   - Define all supported providers
   - Set cost per 1k tokens
   - Define capabilities matrix
   - Configure fallback chains

3. **Story-Level Overrides** (PRD format)
   ```json
   {
     "id": "US-006",
     "preferred_provider": "litellm/gpt-4o",
     "required_capabilities": ["tools", "json_mode"]
   }
   ```

### Phase 5: Testing & Documentation (4 hours)

1. **Integration Tests** (`tests/multi_provider_test.sh`)
   - Test complexity-based routing
   - Test fallback chain behavior
   - Test cost tracking accuracy
   - Test provider failure handling
   - Test capability filtering

2. **Documentation** (`docs/features/multi-provider-llm.md`)
   - Setup guide
   - Provider configuration
   - Cost optimization strategies
   - Fallback chain configuration
   - Troubleshooting guide

## Testing Strategy

### Unit Tests
- Provider selection logic (all complexity levels)
- Fallback chain execution
- Cost calculation accuracy
- Capability filtering

### Integration Tests
- End-to-end provider routing
- Real API calls to multiple providers
- Fallback on provider failures
- Cost tracking persistence

### Performance Tests
- Provider selection overhead (<50ms requirement)
- Latency comparison across providers
- Fallback chain latency

### Error Injection Tests
- Simulated provider failures
- Rate limit handling
- Timeout handling
- Invalid API key handling

## Success Criteria

1. **Functional**:
   - LiteLLM provider working with 5+ models tested
   - Provider selection completes in <50ms
   - Fallback chain works correctly
   - Cost tracking accurate to within 1%

2. **Performance**:
   - No regression in success rate
   - Provider selection adds <5% overhead
   - 30-50% cost reduction on diverse workloads

3. **Reliability**:
   - Fallback chain handles 100% of provider failures
   - No unhandled exceptions
   - Graceful degradation to Claude Code CLI

4. **Documentation**:
   - Complete setup guide
   - Working examples
   - Troubleshooting section
   - Cost optimization guide

## Risks & Mitigation

### High Risk: LiteLLM API Inconsistencies
- **Risk**: Different providers may have inconsistent behavior through LiteLLM
- **Mitigation**: Extensive testing with top 10 providers, fallback to direct providers, comprehensive error handling

### Medium Risk: Cost Tracking Accuracy
- **Risk**: LiteLLM pricing data may be stale or incorrect
- **Mitigation**: Cross-reference with provider APIs, manual audits, configurable cost overrides

### Low Risk: Provider Selection Overhead
- **Risk**: Selection logic may add latency
- **Mitigation**: Cache provider configs, pre-compute capability matrix, <50ms requirement enforced

## Rollout Plan

1. **Week 1**: Implement LiteLLM provider + basic selection logic
2. **Week 2**: Add fallback chains + cost tracking
3. **Week 3**: Testing + documentation
4. **Validation**: Test on 10 real tasks, measure cost reduction
5. **Production**: Enable via feature flag for opt-in usage

## Open Questions

1. Should we auto-detect LiteLLM's supported models or maintain a manual list?
   - **Decision**: Manual list for stability, auto-detect as experimental feature

2. What should be the default fallback chain?
   - **Decision**: `[selected, claude-sonnet, claude-code-cli]`

3. Should we cache provider selection decisions?
   - **Decision**: No caching initially (complexity may change during execution)

## Appendix: LiteLLM Models Matrix

| Complexity | Cheap (<$1/M) | Medium ($1-5/M) | Powerful (>$5/M) |
|------------|---------------|-----------------|------------------|
| 0-2        | gpt-4o-mini, gemini-flash, haiku | - | - |
| 3-5        | - | gpt-4o, gemini-pro, sonnet | - |
| 6-10       | - | - | o1, opus, gemini-thinking |

**Capabilities Matrix**:
- Vision: gpt-4o, gemini-*, opus, sonnet
- Tools: all models except o1-preview
- JSON Mode: gpt-4o, gemini-pro, sonnet

