#!/usr/bin/env python3
"""
MCP Client for claude-loop

Manages connections to MCP servers and provides tool invocation interface.

Usage:
    python3 lib/mcp_client.py list
    python3 lib/mcp_client.py call --server filesystem --tool read_file --params '{"path": "README.md"}'
"""

import json
import os
import sys
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import asyncio


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

    def __post_init__(self):
        if self.tools_whitelist is None:
            self.tools_whitelist = []


class MCPClient:
    """MCP client for claude-loop."""

    def __init__(self, config_path: str = ".claude-loop/mcp-config.json"):
        self.config_path = config_path
        self.servers: Dict[str, MCPServer] = {}
        self.sessions: Dict[str, Any] = {}
        self.tool_schemas: Dict[str, Dict] = {}  # {server/tool: schema}
        self.mcp_available = self._check_mcp_available()

    def _check_mcp_available(self) -> bool:
        """Check if mcp library is available."""
        try:
            import mcp
            return True
        except ImportError:
            return False

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
        if not self.mcp_available:
            print("WARNING: mcp library not available. Install with: pip install mcp==1.13.1", file=sys.stderr)
            return

        server = self.servers.get(server_name)
        if not server:
            raise ValueError(f"Server not configured: {server_name}")

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            if server.transport == "stdio":
                # Parse command and args
                cmd_parts = server.endpoint.split()
                server_params = StdioServerParameters(
                    command=cmd_parts[0],
                    args=cmd_parts[1:] if len(cmd_parts) > 1 else [],
                    env=None
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

                        # Note: session is closed after context manager exits
                        # For persistent connections, need different architecture
            else:
                raise NotImplementedError(f"Transport {server.transport} not yet supported")

        except Exception as e:
            print(f"ERROR connecting to {server_name}: {e}", file=sys.stderr)
            raise

    async def list_tools(self) -> Dict[str, List[Dict]]:
        """List all available tools from all enabled servers."""
        tools_by_server = {}

        for server_name, server in self.servers.items():
            if not server.enabled:
                continue

            try:
                # Clear cached schemas for this server
                self.tool_schemas = {
                    k: v for k, v in self.tool_schemas.items()
                    if not k.startswith(f"{server_name}/")
                }

                # Reconnect and fetch schemas
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
                print(f"WARNING: Failed to connect to {server_name}: {e}", file=sys.stderr)
                tools_by_server[server_name] = []

        return tools_by_server

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server."""
        if not self.mcp_available:
            return {
                "success": False,
                "error": "mcp library not available",
                "content": []
            }

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

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            if server.transport == "stdio":
                # Parse command and args
                cmd_parts = server.endpoint.split()
                server_params = StdioServerParameters(
                    command=cmd_parts[0],
                    args=cmd_parts[1:] if len(cmd_parts) > 1 else [],
                    env=None
                )

                # Create stdio client session
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        # Call tool via MCP
                        result = await session.call_tool(tool_name, params)

                        return {
                            "success": True,
                            "content": result.content,
                            "isError": result.isError if hasattr(result, "isError") else False
                        }
            else:
                raise NotImplementedError(f"Transport {server.transport} not yet supported")

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": []
            }


def main():
    """CLI for testing MCP client."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Client CLI")
    parser.add_argument("command", choices=["list", "call"])
    parser.add_argument("--server", help="Server name")
    parser.add_argument("--tool", help="Tool name")
    parser.add_argument("--params", help="JSON params")
    parser.add_argument("--config", default=".claude-loop/mcp-config.json", help="Config file path")

    args = parser.parse_args()

    client = MCPClient(config_path=args.config)

    try:
        client.load_config()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Create a config file first. Example:", file=sys.stderr)
        print("""
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "npx -y @modelcontextprotocol/server-filesystem .",
      "transport": "stdio",
      "enabled": true,
      "tools_whitelist": ["read_file", "list_directory"]
    }
  ]
}
""", file=sys.stderr)
        sys.exit(1)

    if args.command == "list":
        tools = asyncio.run(client.list_tools())
        print(json.dumps(tools, indent=2))

    elif args.command == "call":
        if not args.server or not args.tool:
            print("ERROR: --server and --tool required for call", file=sys.stderr)
            sys.exit(1)

        params = json.loads(args.params) if args.params else {}
        result = asyncio.run(client.call_tool(args.server, args.tool, params))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
