# Epiloop Docker Image
# Multi-LLM support: Claude, OpenAI, Gemini, Qwen, Codex, Kimi via OpenRouter

FROM node:22-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate

# Create non-root user
RUN useradd -m -s /bin/bash epiloop \
    && mkdir -p /home/epiloop/.epiloop \
    && chown -R epiloop:epiloop /home/epiloop

WORKDIR /app

# Copy epiloop source and build
# Note: In production, you'd COPY from context or use multi-stage
# For local dev, we mount /source read-only and run from there

# Copy package files first for layer caching
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY scripts ./scripts

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy rest of source
COPY . .

# Build
RUN pnpm build

# Create workspace directory for agent outputs
RUN mkdir -p /workspace && chown epiloop:epiloop /workspace

# Switch to non-root user
USER epiloop

# Default environment
ENV NODE_ENV=production
ENV EPILOOP_BIND=0.0.0.0
ENV EPILOOP_PORT=18789

# Expose gateway port
EXPOSE 18789

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:18789/health || exit 1

# Default command: run gateway
CMD ["node", "dist/entry.js", "gateway", "run"]
