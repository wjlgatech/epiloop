# Epiloop Docker Setup (Safe Mode)

Run epiloop in Docker with your code mounted **read-only**. Agents can read your code but all changes are isolated to Docker volumes.

## Quick Start

```bash
# 1. Copy env template
cp .env.example .env

# 2. Generate gateway token
echo "EPILOOP_GATEWAY_TOKEN=$(openssl rand -hex 32)" >> .env

# 3. Add your API key (at least one)
echo "ANTHROPIC_API_KEY=your-key-here" >> .env

# 4. Set your epiloop source path
echo "EPILOOP_SOURCE_PATH=/Users/jialiang.wu/Documents/Projects/epiloop" >> .env

# 5. Build and run
docker compose up -d --build

# 6. Get dashboard URL with token
docker compose run --rm --profile cli epiloop-cli dashboard --no-open
```

## How It Works

```
Your Mac (safe)                     Docker (isolated)
─────────────────                   ─────────────────────
/Users/.../epiloop ──(read-only)──► /source
                                    /workspace ◄── Agent writes here
                                    /home/node/.epiloop ◄── Config
```

- ✅ Agents can **read** your epiloop source code
- ✅ Agents can **write** to `/workspace` (Docker volume)
- ❌ Agents **cannot modify** your source code
- ❌ Agents **cannot access** other files on your Mac

## LLM Provider Support

| Provider | API Key Variable | Models |
|----------|------------------|--------|
| **Anthropic** | `ANTHROPIC_API_KEY` | Claude Opus/Sonnet/Haiku |
| **OpenAI** | `OPENAI_API_KEY` | GPT-4, GPT-4o, Codex |
| **Google** | `GOOGLE_API_KEY` | Gemini Pro, Gemini Flash |
| **OpenRouter** | `OPENROUTER_API_KEY` | 100+ models (Qwen, Kimi, DeepSeek, etc.) |

### Using Qwen, Kimi, or Other Models

Use OpenRouter to access models not directly supported:

```bash
# Add OpenRouter key
echo "OPENROUTER_API_KEY=sk-or-..." >> .env
```

Available via OpenRouter:
- `qwen/qwen-2.5-coder` - Qwen 2.5 Coder
- `deepseek/deepseek-coder` - DeepSeek Coder
- `01-ai/yi-large` - Yi Large
- `mistralai/codestral-latest` - Codestral

## Commands

```bash
# Start gateway (background)
docker compose up -d

# View logs
docker compose logs -f

# Run CLI commands
docker compose run --rm --profile cli epiloop-cli agent --message "hello"

# Start autonomous coding
docker compose run --rm --profile cli epiloop-cli epiloop start "Add feature X"

# Check status
docker compose run --rm --profile cli epiloop-cli epiloop status

# Stop
docker compose down

# Full reset (delete volumes)
docker compose down -v
```

## Retrieving Agent Output

Agent-generated files are in the `epiloop-workspace` volume:

```bash
# List workspace contents
docker compose run --rm --profile cli epiloop-cli exec ls -la /workspace

# Copy files out of container
docker cp $(docker compose ps -q epiloop-gateway):/workspace/my-feature ./my-feature

# Or mount workspace to a host folder (edit docker-compose.yml):
# - ./agent-output:/workspace
```

## Safety Settings

Default sandbox config (in `~/.epiloop/config/agents.json`):

```json5
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "agent",
        "workspaceAccess": "ro",
        "docker": {
          "readOnlyRoot": true,
          "network": "none",
          "capDrop": ["ALL"]
        }
      }
    }
  }
}
```

## Troubleshooting

### "Permission denied" on workspace
```bash
docker compose run --rm --profile cli epiloop-cli exec chown -R 1000:1000 /workspace
```

### Container won't start
```bash
docker compose logs epiloop-gateway
```

### Need to rebuild after code changes
```bash
docker compose build --no-cache
docker compose up -d
```
