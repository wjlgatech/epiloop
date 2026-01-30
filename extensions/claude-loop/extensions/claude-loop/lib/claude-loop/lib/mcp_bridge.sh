#!/bin/bash
#
# mcp_bridge.sh - Bridge between claude-loop and MCP client
#
# This script provides integration functions to:
# - Parse MCP tool calls from prompts
# - Execute MCP tools via Python client
# - List available MCP tools
# - Initialize and validate MCP configuration
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Path to mcp_client.py
MCP_CLIENT="${MCP_CLIENT:-lib/mcp_client.py}"
MCP_CONFIG_FILE="${MCP_CONFIG_FILE:-.claude-loop/mcp-config.json}"

# ============================================================================
# Initialization and Validation
# ============================================================================

# Check if MCP is enabled via environment variable
mcp_is_enabled() {
    [[ "${ENABLE_MCP:-false}" == "true" ]]
}

# Initialize MCP (validate config exists and mcp library installed)
mcp_init() {
    if ! mcp_is_enabled; then
        return 0
    fi

    # Check if config file exists
    if [[ ! -f "$MCP_CONFIG_FILE" ]]; then
        echo "WARNING: MCP enabled but config not found: $MCP_CONFIG_FILE" >&2
        echo "Creating example config..." >&2

        mkdir -p "$(dirname "$MCP_CONFIG_FILE")"
        cat > "$MCP_CONFIG_FILE" <<'EOF'
{
  "servers": [
    {
      "name": "filesystem",
      "endpoint": "npx -y @modelcontextprotocol/server-filesystem .",
      "transport": "stdio",
      "auth_type": "none",
      "enabled": false,
      "tools_whitelist": ["read_file", "list_directory", "search_files"],
      "readonly": true
    },
    {
      "name": "sqlite",
      "endpoint": "npx -y @modelcontextprotocol/server-sqlite data.db",
      "transport": "stdio",
      "auth_type": "none",
      "enabled": false,
      "tools_whitelist": ["query", "list_tables", "describe_table"],
      "readonly": true
    }
  ],
  "global_settings": {
    "timeout_seconds": 30,
    "max_retries": 2,
    "cache_tool_schemas": true,
    "schema_cache_ttl_seconds": 3600
  }
}
EOF
        echo "Example config created at $MCP_CONFIG_FILE" >&2
        echo "Edit the file and set enabled=true for servers you want to use." >&2
        return 1
    fi

    # Validate mcp library installed
    if ! python3 -c "import mcp" 2>/dev/null; then
        echo "ERROR: mcp library not installed" >&2
        echo "Run: pip install mcp==1.13.1" >&2
        return 1
    fi

    echo "MCP initialized successfully" >&2
    return 0
}

# ============================================================================
# Tool Listing
# ============================================================================

# List all available MCP tools from configured servers
mcp_list_tools() {
    if ! mcp_is_enabled; then
        echo '{"error": "MCP not enabled. Use --enable-mcp flag."}'
        return 1
    fi

    if [[ ! -f "$MCP_CLIENT" ]]; then
        echo '{"error": "MCP client not found at '"$MCP_CLIENT"'"}'
        return 1
    fi

    python3 "$MCP_CLIENT" list --config "$MCP_CONFIG_FILE" 2>&1
}

# ============================================================================
# Tool Invocation
# ============================================================================

# Execute MCP tool call
# Args: server_name tool_name params_json
mcp_call_tool() {
    local server="$1"
    local tool="$2"
    local params="$3"

    if ! mcp_is_enabled; then
        echo '{"success": false, "error": "MCP not enabled"}'
        return 1
    fi

    if [[ ! -f "$MCP_CLIENT" ]]; then
        echo '{"success": false, "error": "MCP client not found"}'
        return 1
    fi

    # Call Python MCP client
    python3 "$MCP_CLIENT" call \
        --server "$server" \
        --tool "$tool" \
        --params "$params" \
        --config "$MCP_CONFIG_FILE" \
        2>&1
}

# ============================================================================
# Prompt Processing
# ============================================================================

# Parse MCP calls from prompt text
# Format: [use-mcp:server/tool:{json_params}]
# Returns: JSON array of parsed calls
parse_mcp_call() {
    local prompt_text="$1"

    # Extract MCP calls using grep
    # Example: [use-mcp:filesystem/read_file:{"path": "/etc/hosts"}]
    local mcp_calls=$(echo "$prompt_text" | grep -o '\[use-mcp:[^]]*\]' || echo "")

    if [[ -z "$mcp_calls" ]]; then
        echo "[]"
        return 0
    fi

    # Parse into JSON array
    local json_array="["
    local first=true

    while IFS= read -r call; do
        [[ -z "$call" ]] && continue

        # Remove brackets
        call="${call#\[use-mcp:}"
        call="${call%\]}"

        # Split server/tool:params
        # Handle case where params might contain ':'
        local server_tool_part="${call%%:*}"
        local params_part="${call#*:}"

        # Split server and tool
        local server="${server_tool_part%%/*}"
        local tool="${server_tool_part#*/}"

        if [[ "$first" == true ]]; then
            first=false
        else
            json_array+=","
        fi

        # params_part should already be valid JSON
        json_array+=$(cat <<EOF

{
  "server": "$server",
  "tool": "$tool",
  "params": $params_part
}
EOF
)
    done <<< "$mcp_calls"

    json_array+=$'\n]'
    echo "$json_array"
}

# Process MCP calls in a prompt and replace them with results
# Args: prompt_text
# Returns: prompt with [use-mcp:...] replaced by tool results
process_mcp_calls_in_prompt() {
    local prompt="$1"

    if ! mcp_is_enabled; then
        echo "$prompt"
        return 0
    fi

    # Parse MCP calls
    local mcp_calls=$(parse_mcp_call "$prompt")

    # Check if any calls found
    if [[ "$mcp_calls" == "[]" ]]; then
        echo "$prompt"
        return 0
    fi

    # Execute each call and replace in prompt
    echo "$mcp_calls" | jq -c '.[]' 2>/dev/null | while read -r call; do
        local server=$(echo "$call" | jq -r '.server')
        local tool=$(echo "$call" | jq -r '.tool')
        local params=$(echo "$call" | jq -r '.params')

        # Execute tool
        local result=$(mcp_call_tool "$server" "$tool" "$params")

        # Extract content from result
        local content=$(echo "$result" | jq -r '.content // .error // "No result"' 2>/dev/null)

        # Replace in prompt
        # Note: This is a simplified replacement - may need refinement
        local mcp_tag="\[use-mcp:${server}/${tool}:.*\]"
        prompt=$(echo "$prompt" | sed "s|$mcp_tag|$content|g")
    done

    echo "$prompt"
}

# ============================================================================
# Utility Functions
# ============================================================================

# Get MCP configuration path
mcp_get_config_path() {
    echo "$MCP_CONFIG_FILE"
}

# Check if MCP client is available
mcp_client_available() {
    [[ -f "$MCP_CLIENT" ]] && python3 -c "import mcp" 2>/dev/null
}

# Get MCP status for debugging
mcp_status() {
    echo "MCP Status:"
    echo "  Enabled: $(mcp_is_enabled && echo 'yes' || echo 'no')"
    echo "  Config: $MCP_CONFIG_FILE ($([ -f "$MCP_CONFIG_FILE" ] && echo 'exists' || echo 'missing'))"
    echo "  Client: $MCP_CLIENT ($([ -f "$MCP_CLIENT" ] && echo 'exists' || echo 'missing'))"
    echo "  Library: $(python3 -c 'import mcp; print("installed")' 2>/dev/null || echo 'not installed')"
}

# ============================================================================
# Main (for testing)
# ============================================================================

# If script is run directly (not sourced), run tests
if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]]; then
    echo "MCP Bridge Test Mode"
    echo "===================="
    echo

    # Test 1: Status
    echo "Test 1: MCP Status"
    mcp_status
    echo

    # Test 2: Parse MCP call
    echo "Test 2: Parse MCP call"
    test_prompt='Use [use-mcp:filesystem/read_file:{"path": "README.md"}] to read the file.'
    parsed=$(parse_mcp_call "$test_prompt")
    echo "Parsed: $parsed"
    echo

    # Test 3: List tools (if enabled)
    if mcp_is_enabled; then
        echo "Test 3: List MCP tools"
        mcp_list_tools
    else
        echo "Test 3: Skipped (MCP not enabled - set ENABLE_MCP=true)"
    fi
fi
