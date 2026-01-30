# MCP Integration Design

**Date:** 2026-01-20
**Story:** US-005 - Integrate MCP (Model Context Protocol)
**Status:** Design Complete

## Overview

Integrate Model Context Protocol (MCP) to enable claude-loop to access a rich ecosystem of community tools for database access, filesystem operations, API interactions, and cloud services. This design vendors the `mcp` library and creates a bridge layer that translates between MCP's JSON-RPC format and claude-loop's prompt-based tool invocation system.

## Goals

1. **Extensibility**: Enable access to 100+ community MCP servers without modifying claude-loop core
2. **Safety**: Enforce read-only operations by default, with explicit whitelisting for write operations
3. **Integration**: Seamless bridge between MCP tools and claude-loop's existing skills framework
4. **Performance**: Tool discovery and invocation adds <100ms overhead per call
5. **Developer Experience**: Simple configuration, clear error messages, comprehensive documentation

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     claude-loop                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐         ┌─────────────────┐            │
│  │  Prompt        │────────▶│  MCP Bridge     │            │
│  │  Processor     │         │  Layer          │            │
│  └────────────────┘         └────────┬────────┘            │
│         │                             │                      │
│         │  [use-mcp:server/tool]     │                      │
│         │                             │                      │
│         ▼                             ▼                      │
│  ┌────────────────┐         ┌─────────────────┐            │
│  │  Skills        │         │  MCP Client     │            │
│  │  Framework     │         │  (mcp==1.13.1)  │            │
│  └────────────────┘         └────────┬────────┘            │
│                                       │                      │
└───────────────────────────────────────┼──────────────────────┘
                                        │
                                        │ JSON-RPC
                                        ▼
                      ┌────────────────────────────────┐
                      │    MCP Servers                 │
                      ├────────────────────────────────┤
                      │  - filesystem (read-only)      │
                      │  - sqlite (read-only)          │
                      │  - web-search                  │
                      │  - ... (community servers)     │
                      └────────────────────────────────┘
```

### Data Flow

1. **Tool Discovery** (startup):
   ```
   claude-loop.sh --list-mcp-tools
     └─▶ lib/mcp_client.py load_config()
         └─▶ Connect to configured servers
             └─▶ Query server.listTools()
                 └─▶ Cache tool schemas
                     └─▶ Display available tools
   ```

2. **Tool Invocation** (during iteration):
   ```
   Prompt: "Read file using [use-mcp:filesystem/read_file:{path}]"
     └─▶ parse_mcp_call() extracts: server, tool, params
         └─▶ mcp_bridge.call_tool(server, tool, params)
             └─▶ Validate against whitelist + schema
                 └─▶ JSON-RPC call to MCP server
                     └─▶ Format response
                         └─▶ Inject into context
   ```

## Component Design

### 1. Configuration (`.claude-loop/mcp-config.json`)

```json
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "npx -y @modelcontextprotocol/server-filesystem /path/to/allowed/dir",
      "transport": "stdio",
      "auth_type": "none",
      "enabled": true,
      "tools_whitelist": [
        "read_file",
        "list_directory",
        "search_files"
      ],
      "readonly": true
    },
    {
      "name": "sqlite",
      "endpoint": "npx -y @modelcontextprotocol/server-sqlite /path/to/db.sqlite",
      "transport": "stdio",
      "auth_type": "none",
      "enabled": true,
      "tools_whitelist": [
        "query",
        "list_tables",
        "describe_table"
      ],
      "readonly": true
    },
    {
      "name": "web-search",
      "endpoint": "http://localhost:3100/mcp",
      "transport": "http",
      "auth_type": "bearer",
      "auth_token": "${WEB_SEARCH_API_KEY}",
      "enabled": false,
      "tools_whitelist": ["search"]
    }
  ],
  "global_settings": {
    "timeout_seconds": 30,
    "max_retries": 2,
    "cache_tool_schemas": true,
    "schema_cache_ttl_seconds": 3600
  }
}
```

### 2. MCP Client (`lib/mcp_client.py`)

```python
#!/usr/bin/env python3
"""
MCP Client for claude-loop

Manages connections to MCP servers and provides tool invocation interface.
"""

import json
import os
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import asyncio

# Vendor mcp library
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("ERROR: mcp library not installed. Run: pip install mcp==1.13.1")
    sys.exit(1)


@dataclass
class MCPServer:
    """Configuration for a single MCP server."""
    name: str
    endpoint: str
    transport: str  # "stdio" or "http"
    auth_type: str  # "none", "bearer", "basic"
    auth_token: Optional[str] = None
    enabled: bool = True
    tools_whitelist: List[str] = None
    readonly: bool = True


class MCPClient:
    """MCP client for claude-loop."""

    def __init__(self, config_path: str = ".claude-loop/mcp-config.json"):
        self.config_path = config_path
        self.servers: Dict[str, MCPServer] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tool_schemas: Dict[str, Dict] = {}  # {server/tool: schema}

    def load_config(self) -> None:
        """Load MCP configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"MCP config not found: {self.config_path}")

        with open(self.config_path) as f:
            config = json.load(f)

        for server_config in config.get("servers", []):
            if not server_config.get("enabled", True):
                continue

            server = MCPServer(
                name=server_config["name"],
                endpoint=server_config["endpoint"],
                transport=server_config.get("transport", "stdio"),
                auth_type=server_config.get("auth_type", "none"),
                auth_token=self._resolve_env_var(server_config.get("auth_token")),
                enabled=server_config.get("enabled", True),
                tools_whitelist=server_config.get("tools_whitelist", []),
                readonly=server_config.get("readonly", True)
            )
            self.servers[server.name] = server

    def _resolve_env_var(self, value: Optional[str]) -> Optional[str]:
        """Resolve ${VAR} environment variables."""
        if not value:
            return None
        if value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var)
        return value

    async def connect_server(self, server_name: str) -> None:
        """Connect to an MCP server and cache tool schemas."""
        server = self.servers.get(server_name)
        if not server:
            raise ValueError(f"Server not configured: {server_name}")

        if server.transport == "stdio":
            # Parse command and args
            cmd_parts = server.endpoint.split()
            server_params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:] if len(cmd_parts) > 1 else []
            )

            # Create stdio client session
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Cache tool schemas
                    tools_result = await session.list_tools()
                    for tool in tools_result.tools:
                        tool_key = f"{server_name}/{tool.name}"
                        self.tool_schemas[tool_key] = {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }

                    self.sessions[server_name] = session
        else:
            raise NotImplementedError(f"Transport {server.transport} not yet supported")

    async def list_tools(self) -> Dict[str, List[Dict]]:
        """List all available tools from all enabled servers."""
        tools_by_server = {}

        for server_name, server in self.servers.items():
            if not server.enabled:
                continue

            try:
                await self.connect_server(server_name)
                server_tools = [
                    schema for key, schema in self.tool_schemas.items()
                    if key.startswith(f"{server_name}/")
                ]

                # Apply whitelist filter
                if server.tools_whitelist:
                    server_tools = [
                        t for t in server_tools
                        if t["name"] in server.tools_whitelist
                    ]

                tools_by_server[server_name] = server_tools
            except Exception as e:
                print(f"WARNING: Failed to connect to {server_name}: {e}")
                tools_by_server[server_name] = []

        return tools_by_server

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server."""
        server = self.servers.get(server_name)
        if not server:
            raise ValueError(f"Server not configured: {server_name}")

        if not server.enabled:
            raise RuntimeError(f"Server disabled: {server_name}")

        # Validate against whitelist
        if server.tools_whitelist and tool_name not in server.tools_whitelist:
            raise PermissionError(
                f"Tool {tool_name} not in whitelist for {server_name}"
            )

        # Get or create session
        if server_name not in self.sessions:
            await self.connect_server(server_name)

        session = self.sessions[server_name]

        # Validate schema
        tool_key = f"{server_name}/{tool_name}"
        if tool_key not in self.tool_schemas:
            raise ValueError(f"Tool not found: {tool_key}")

        # Call tool via MCP
        result = await session.call_tool(tool_name, params)

        return {
            "success": True,
            "content": result.content,
            "isError": result.isError if hasattr(result, "isError") else False
        }


def main():
    """CLI for testing MCP client."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="MCP Client CLI")
    parser.add_argument("command", choices=["list", "call"])
    parser.add_argument("--server", help="Server name")
    parser.add_argument("--tool", help="Tool name")
    parser.add_argument("--params", help="JSON params")

    args = parser.parse_args()

    client = MCPClient()
    client.load_config()

    if args.command == "list":
        tools = asyncio.run(client.list_tools())
        print(json.dumps(tools, indent=2))
    elif args.command == "call":
        if not args.server or not args.tool:
            print("ERROR: --server and --tool required for call")
            sys.exit(1)
        params = json.loads(args.params) if args.params else {}
        result = asyncio.run(client.call_tool(args.server, args.tool, params))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

### 3. MCP Bridge Layer (`lib/mcp_bridge.sh`)

```bash
#!/bin/bash
#
# mcp_bridge.sh - Bridge between claude-loop and MCP client
#

set -euo pipefail

# Source path to mcp_client.py
MCP_CLIENT="${MCP_CLIENT:-lib/mcp_client.py}"

# Parse MCP call from prompt
# Format: [use-mcp:server/tool:{json_params}]
parse_mcp_call() {
    local prompt_text="$1"

    # Extract MCP calls using regex
    # Example: [use-mcp:filesystem/read_file:{"path": "/etc/hosts"}]
    local mcp_calls=$(echo "$prompt_text" | grep -o '\[use-mcp:[^]]*\]' || true)

    if [[ -z "$mcp_calls" ]]; then
        echo "[]"
        return 0
    fi

    # Parse into JSON array
    local json_array="["
    local first=true

    while IFS= read -r call; do
        # Remove brackets
        call="${call#\[use-mcp:}"
        call="${call%\]}"

        # Split server/tool:params
        local server_tool="${call%%:*}"
        local params="${call#*:}"

        local server="${server_tool%%/*}"
        local tool="${server_tool#*/}"

        if [[ "$first" == true ]]; then
            first=false
        else
            json_array+=","
        fi

        json_array+=$(cat <<EOF

{
  "server": "$server",
  "tool": "$tool",
  "params": $params
}
EOF
)
    done <<< "$mcp_calls"

    json_array+=$'\n]'
    echo "$json_array"
}

# Execute MCP tool call
mcp_call_tool() {
    local server="$1"
    local tool="$2"
    local params="$3"

    # Call Python MCP client
    python3 "$MCP_CLIENT" call \
        --server "$server" \
        --tool "$tool" \
        --params "$params" \
        2>&1
}

# List all available MCP tools
mcp_list_tools() {
    python3 "$MCP_CLIENT" list 2>&1
}

# Check if MCP is enabled
mcp_is_enabled() {
    [[ "${ENABLE_MCP:-false}" == "true" ]]
}

# Initialize MCP (validate config exists)
mcp_init() {
    if ! mcp_is_enabled; then
        return 0
    fi

    local config_file=".claude-loop/mcp-config.json"

    if [[ ! -f "$config_file" ]]; then
        echo "WARNING: MCP enabled but config not found: $config_file"
        echo "Creating example config..."

        mkdir -p "$(dirname "$config_file")"
        cat > "$config_file" <<'EOF'
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "npx -y @modelcontextprotocol/server-filesystem .",
      "transport": "stdio",
      "auth_type": "none",
      "enabled": false,
      "tools_whitelist": ["read_file", "list_directory"],
      "readonly": true
    }
  ],
  "global_settings": {
    "timeout_seconds": 30,
    "max_retries": 2
  }
}
EOF
        echo "Example config created. Edit and enable servers."
        return 1
    fi

    # Validate mcp library installed
    if ! python3 -c "import mcp" 2>/dev/null; then
        echo "ERROR: mcp library not installed"
        echo "Run: pip install mcp==1.13.1"
        return 1
    fi

    return 0
}
```

### 4. Integration with claude-loop.sh

Add to `claude-loop.sh`:

```bash
# Source MCP bridge if enabled
if [[ "${ENABLE_MCP:-false}" == "true" ]]; then
    source lib/mcp_bridge.sh

    # Initialize MCP
    if mcp_init; then
        echo "MCP initialized successfully"
    else
        echo "WARNING: MCP initialization failed, continuing without MCP"
        ENABLE_MCP=false
    fi
fi

# Add --list-mcp-tools flag
if [[ "${LIST_MCP_TOOLS:-false}" == "true" ]]; then
    mcp_list_tools
    exit 0
fi

# In prompt processing: replace [use-mcp:...] with tool results
process_mcp_calls_in_prompt() {
    local prompt="$1"

    if ! mcp_is_enabled; then
        echo "$prompt"
        return 0
    fi

    # Parse MCP calls
    local mcp_calls=$(parse_mcp_call "$prompt")

    # Execute each call and replace in prompt
    echo "$mcp_calls" | jq -c '.[]' | while read -r call; do
        local server=$(echo "$call" | jq -r '.server')
        local tool=$(echo "$call" | jq -r '.tool')
        local params=$(echo "$call" | jq -r '.params')

        # Execute tool
        local result=$(mcp_call_tool "$server" "$tool" "$params")

        # Replace in prompt
        local mcp_tag="[use-mcp:${server}/${tool}:${params}]"
        prompt="${prompt//$mcp_tag/$result}"
    done

    echo "$prompt"
}
```

## Error Handling

1. **Server Unavailable**: Log warning, continue without tool, don't fail iteration
2. **Tool Not Whitelisted**: Error with clear message, suggest adding to whitelist
3. **Invalid Schema**: Validate params before calling, return schema validation error
4. **Timeout**: Configurable timeout (30s default), return timeout error
5. **Auth Failure**: Clear error message with env var hint

## Security Model

1. **Read-Only Default**: All servers start as readonly=true
2. **Explicit Whitelist**: Only whitelisted tools callable
3. **Schema Validation**: Validate all params against MCP tool schema
4. **Sandboxing**: MCP servers run as separate processes (stdio transport)
5. **Write Operations**: Require explicit user approval or separate `tools_write_whitelist`

## Testing Strategy

Integration test (`tests/mcp_test.sh`):

```bash
#!/bin/bash
# Test MCP integration

# Test 1: Tool discovery
echo "Test 1: List MCP tools"
./claude-loop.sh --enable-mcp --list-mcp-tools

# Test 2: Tool invocation (filesystem read)
echo "Test 2: Read file via MCP"
# Create test prompt with [use-mcp:filesystem/read_file:{"path": "README.md"}]

# Test 3: Error handling (unavailable server)
echo "Test 3: Unavailable server fallback"
# Disable server, verify graceful fallback

# Test 4: Whitelist enforcement
echo "Test 4: Whitelist enforcement"
# Try calling non-whitelisted tool, verify rejection

# Test 5: Schema validation
echo "Test 5: Schema validation"
# Invalid params, verify error
```

## Documentation Deliverables

1. **Setup Guide**: `docs/features/mcp-integration.md` (2000+ lines)
   - Installation steps
   - Configuration examples
   - Server setup for filesystem, sqlite, web-search
   - Custom server integration

2. **Security Model**: Whitelist management, readonly vs write operations

3. **Troubleshooting**: Common errors and solutions

4. **Example Configurations**: `.claude-loop/mcp-config.example.json`

## Performance Targets

- Tool discovery: <500ms for 3 servers with 10 tools each
- Tool invocation: <100ms overhead (excluding tool execution time)
- Schema caching: Reduce repeated discovery calls

## Migration Path

1. Install mcp library: `pip install mcp==1.13.1`
2. Create config: Copy example config to `.claude-loop/mcp-config.json`
3. Enable MCP: Run with `--enable-mcp` flag
4. Test tools: `./claude-loop.sh --list-mcp-tools`
5. Use in prompts: Add `[use-mcp:server/tool:{params}]` syntax

## Future Enhancements (Out of Scope for US-005)

- HTTP transport support (currently stdio only)
- Tool result caching
- Parallel tool execution
- MCP server health monitoring
- Auto-discovery of local MCP servers

## Implementation Checklist

- [ ] Add mcp==1.13.1 to requirements.txt
- [ ] Create lib/mcp_client.py with MCPClient class
- [ ] Create lib/mcp_bridge.sh with parse/call functions
- [ ] Create .claude-loop/mcp-config.example.json
- [ ] Integrate into claude-loop.sh (mcp_init, process_mcp_calls)
- [ ] Add --enable-mcp and --list-mcp-tools flags
- [ ] Create tests/mcp_test.sh integration tests
- [ ] Write docs/features/mcp-integration.md (2000+ lines)
- [ ] Configure example servers: filesystem, sqlite, web-search
- [ ] Validate all 13 acceptance criteria from PRD

## Conclusion

This design provides a robust, secure, and extensible MCP integration that aligns with claude-loop's philosophy of vendoring proven libraries while maintaining safety and simplicity. The bridge architecture keeps MCP concerns isolated and allows gradual adoption via feature flags.

**Ready for implementation: Yes**
**Estimated implementation time: 20 hours** (matches PRD estimate)
**Risk level: Medium** (dependency on external MCP servers, but mitigated with fallbacks)
