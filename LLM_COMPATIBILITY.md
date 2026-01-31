# Epiloop LLM Compatibility

## Overview

Epiloop has **two LLM integration points** with different provider support:

| Component | Purpose | Default | Configurable? |
|-----------|---------|---------|---------------|
| **PRD Generator** | Converts natural language → structured requirements | Claude Sonnet | ⚠️ Hardcoded |
| **Agent Runtime** | Executes coding tasks, tool use, reasoning | Claude Sonnet | ✅ Yes |

## What Works Out of the Box

### Agent Runtime (PI Framework)

The agent runtime uses `@mariozechner/pi-agent-core` which supports:

| Provider | Status | API Key Variable | Notes |
|----------|--------|------------------|-------|
| **Anthropic Claude** | ✅ Full | `ANTHROPIC_API_KEY` | Best supported |
| **OpenAI GPT-4** | ✅ Full | `OPENAI_API_KEY` | Works well |
| **Google Gemini** | ✅ Full | `GOOGLE_API_KEY` | Works well |
| **GitHub Copilot** | ⚠️ Partial | OAuth flow | Needs manual setup |
| **AWS Bedrock** | ⚠️ Partial | AWS credentials | Needs IAM config |
| **Ollama (local)** | ✅ Works | None (local) | Set `OLLAMA_HOST` |

### PRD Generator

**Currently hardcoded to Claude Sonnet.** This is in `extensions/claude-loop/src/prd-generator.ts`:

```typescript
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const response = await client.messages.create({
  model: 'claude-sonnet-4-5-20250929',  // Hardcoded
  ...
});
```

**Impact**: You need `ANTHROPIC_API_KEY` even if using other models for coding.

## Using Qwen / Kimi / DeepSeek / Codex

These models are **not directly supported** but can work via OpenRouter:

### Option 1: OpenRouter (Recommended)

OpenRouter provides a unified API to 100+ models:

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
```

Available models:
- `qwen/qwen-2.5-coder-32b-instruct` - Qwen 2.5 Coder
- `deepseek/deepseek-coder` - DeepSeek Coder
- `01-ai/yi-large` - Yi Large (Kimi's base)
- `mistralai/codestral-latest` - Codestral
- `anthropic/claude-3.5-sonnet` - Claude via OpenRouter

Configure in `~/.epiloop/config/agents.json`:
```json5
{
  "agents": {
    "defaults": {
      "model": "openrouter/qwen/qwen-2.5-coder-32b-instruct",
      "authProfile": "openrouter"
    }
  },
  "auth": {
    "profiles": {
      "openrouter": {
        "provider": "openrouter",
        "apiKey": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

### Option 2: Ollama (Local Models)

Run models locally without API keys:

```bash
# Install Ollama on Mac
brew install ollama

# Pull models
ollama pull qwen2.5-coder:32b
ollama pull codellama:34b
ollama pull deepseek-coder:33b
```

Configure epiloop:
```json5
{
  "agents": {
    "defaults": {
      "model": "qwen2.5-coder:32b",
      "authProfile": "ollama"
    }
  },
  "auth": {
    "profiles": {
      "ollama": {
        "provider": "ollama",
        "baseUrl": "http://host.docker.internal:11434"
      }
    }
  }
}
```

**Note**: In Docker, use `host.docker.internal` to reach Ollama on Mac.

## Making PRD Generator Multi-Provider (Code Change Required)

To use non-Claude models for PRD generation, you'd need to modify `extensions/claude-loop/src/prd-generator.ts`:

```typescript
// Current (Claude-only):
import Anthropic from '@anthropic-ai/sdk';
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// Multi-provider (example using OpenAI SDK with OpenRouter):
import OpenAI from 'openai';
const client = new OpenAI({
  apiKey: process.env.OPENROUTER_API_KEY,
  baseURL: 'https://openrouter.ai/api/v1',
});
```

This is a ~20 line change but not currently implemented.

## Recommendation by Use Case

| Use Case | Recommended Setup |
|----------|-------------------|
| **Best quality** | `ANTHROPIC_API_KEY` for everything |
| **Cost-conscious** | Claude for PRD, Qwen/DeepSeek via OpenRouter for coding |
| **Privacy-first** | Ollama locally (slower, needs beefy Mac) |
| **No Anthropic access** | OpenRouter for agent + skip PRD (use manual stories) |

## Current Limitations

1. **PRD generation requires Claude** - hardcoded in `prd-generator.ts`
2. **Kimi API** - Not directly supported (use Yi Large via OpenRouter as proxy)
3. **Codex (OpenAI)** - Deprecated; use GPT-4 instead
4. **Qwen direct API** - Not implemented; use OpenRouter

## Summary

| Model | Direct Support | Via OpenRouter | Via Ollama |
|-------|----------------|----------------|------------|
| Claude | ✅ | ✅ | ❌ |
| GPT-4 | ✅ | ✅ | ❌ |
| Gemini | ✅ | ✅ | ❌ |
| Qwen | ❌ | ✅ | ✅ |
| DeepSeek | ❌ | ✅ | ✅ |
| Kimi/Yi | ❌ | ✅ | ❌ |
| Codex | ❌ (deprecated) | ❌ | ❌ |
| Codestral | ❌ | ✅ | ✅ |
