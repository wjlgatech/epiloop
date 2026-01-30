# Cowork's Integration & Connectors Model

**Analysis Date:** 2026-01-13
**Story:** US-004
**Author:** Claude-Loop Autonomous Analysis

---

## Executive Summary

This document analyzes Claude Cowork's integration and connector architecture, comparing it to claude-loop's current capabilities. **Key finding: Cowork's connector model (MCP-based) provides "plug-and-play" extensibility that claude-loop currently lacks.** While claude-loop excels at autonomous feature implementation with domain-specific agents, it has no standardized mechanism for connecting to external systems, databases, or third-party APIs.

**Strategic Recommendation:** Adopt MCP as claude-loop's integration standard, enabling claude-loop to orchestrate both code implementation AND external system coordination through a unified protocol.

---

## Table of Contents

1. [Cowork's Integration Architecture](#1-coworks-integration-architecture)
2. [Claude Code's MCP Implementation](#2-claude-codes-mcp-implementation)
3. [Browser Integration via Chrome Pairing](#3-browser-integration-via-chrome-pairing)
4. [Claude-Loop's Current Integration Model](#4-claude-loops-current-integration-model)
5. [Gap Analysis](#5-gap-analysis)
6. [MCP-Compatible Architecture Proposal](#6-mcp-compatible-architecture-proposal)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Conclusion](#8-conclusion)

---

## 1. Cowork's Integration Architecture

### 1.1 Connectors Overview

**Connectors** in Cowork are integrations built on the **Model Context Protocol (MCP)**, enabling Claude to interact with external tools, databases, and applications. According to the [Claude Connectors directory](https://claude.com/connectors), connectors are "built and maintained by third-party developers using the Model Context Protocol (MCP)."

**Key Characteristics:**

| Aspect | Description |
|--------|-------------|
| **Protocol** | Built on MCP (open standard) |
| **Ownership** | Third-party maintained |
| **Authentication** | OAuth-based (per-connector terms) |
| **Discovery** | Centralized directory at claude.com/connectors |
| **Compatibility** | Works with Claude, Claude Code, and Cowork |

### 1.2 Connector Categories

Based on the connector directory, available integrations span diverse domains:

#### **Enterprise & Productivity**
- **Asana** - Task coordination
- **Atlassian Rovo** - Jira & Confluence access
- **ClickUp** - Project management
- **Box** - Content management

#### **Data & Analytics**
- **Amplitude** - Data insights
- **Aura** - Company intelligence
- **Blockscout** - Blockchain data

#### **Specialized Domains**
- **Benchling** - R&D data and experiments
- **BioRender** - Scientific templates
- **bioRxiv** - Preprint research
- **10x Genomics Cloud** - Life sciences

#### **Business Tools**
- **ActiveCampaign** - Marketing automation
- **Bitly** - Link management
- **Canva** - Design creation

### 1.3 Healthcare Connectors (2026 Expansion)

Anthropic [announced healthcare-specific connectors](https://fortune.com/2026/01/11/anthropic-unveils-claude-for-healthcare-and-expands-life-science-features-partners-with-healthex-to-let-users-connect-medical-records/) including:

- **CMS Coverage Database** - Medicare & Medicaid coverage
- **ICD-10** - International Classification of Diseases
- **National Provider Identifier Registry**
- **PubMed** - Medical research
- **Medidata** - Clinical trial data
- **ClinicalTrials.gov** - Clinical trial registry
- **HealthEx** - Patient electronic health records

**Strategic Insight:** Anthropic is building **vertical-specific connector ecosystems** for high-value domains (healthcare, life sciences). This suggests a platform strategy where connectors unlock new markets.

### 1.4 Connector Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Claude/Cowork                           │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │             Model Context Protocol (MCP)            │     │
│  └────────────┬──────────────┬──────────────┬──────────┘     │
│               │              │              │                │
│               ▼              ▼              ▼                │
│         ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│         │ Connector│   │ Connector│   │ Connector│          │
│         │  Asana   │   │  GitHub  │   │  Notion  │          │
│         └────┬─────┘   └────┬─────┘   └────┬─────┘          │
│              │              │              │                │
└──────────────┼──────────────┼──────────────┼────────────────┘
               │              │              │
               ▼              ▼              ▼
         ┌──────────┐   ┌──────────┐   ┌──────────┐
         │  Asana   │   │  GitHub  │   │  Notion  │
         │   API    │   │   API    │   │   API    │
         └──────────┘   └──────────┘   └──────────┘
```

**Key Design Principles:**

1. **Standardized Protocol**: All connectors speak MCP, enabling uniform integration
2. **Decentralized Development**: Third-party developers build and maintain connectors
3. **Centralized Discovery**: Directory at claude.com/connectors for discoverability
4. **OAuth Security**: Each connector handles its own authentication via OAuth flows
5. **Cross-Product Compatibility**: Same connectors work across Claude, Claude Code, Cowork

---

## 2. Claude Code's MCP Implementation

### 2.1 MCP Server Configuration

Claude Code connects to MCP servers via configuration file. According to [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp), there are two primary configuration methods:

#### **Configuration File Location**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Alternative: `~/.claude.json` (recommended for consistency)

#### **Configuration via CLI**
```bash
# Add server
claude mcp add [name] --scope user

# List servers
claude mcp list

# Remove server
claude mcp remove [name]

# Test server
claude mcp get [name]
```

#### **Example Configuration: GitHub Server**
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_YOUR_TOKEN"
      }
    }
  }
}
```

#### **HTTP-Based MCP Server**
```bash
claude mcp add --transport http --scope local my-mcp-server \
  https://your-mcp-server.com \
  --env API_KEY="your-api-key-here" \
  --header "API_Key: ${API_KEY}"
```

### 2.2 MCP Transport Types

| Transport | Use Case | Best For |
|-----------|----------|----------|
| **stdio** | Local processes | Command-line tools, scripts |
| **HTTP** | Remote services | Cloud APIs, third-party services |
| **SSE** | Real-time streams | Live data feeds, notifications |

**Recommendation from docs:** HTTP is the most widely supported transport for cloud-based services.

### 2.3 Resource @Mentions

MCP servers expose **resources** that can be referenced using `@mentions`:

```
Type @ in your prompt → see available resources
Resources appear alongside files in autocomplete menu
```

**Example:**
```
@github-issues "Show open issues assigned to me"
@notion-page "Fetch the project roadmap page"
```

This provides a **unified interface** for accessing both local files and remote data sources.

### 2.4 Token Management

Claude Code tracks MCP tool output to prevent context bloat:

- **Warning threshold**: 10,000 tokens per tool output
- **Default maximum**: 25,000 tokens
- **Configurable limits**: Can be adjusted per use case

**Strategic Insight:** This shows Anthropic's awareness of context window management—critical for long-running agentic workflows.

### 2.5 MCP Server Discovery

MCP servers can be managed via:

1. **@Mentioning** - Toggle servers on/off during session
2. **/mcp command** - View and manage all configured servers
3. **Configuration files** - Direct editing for complex setups

---

## 3. Browser Integration via Chrome Pairing

### 3.1 Architecture

Claude Code integrates with Chrome through the **Native Messaging API**. From the [Chrome integration documentation](https://code.claude.com/docs/en/chrome):

```
┌──────────────────────────────────────────────────────────────┐
│                   Claude Code (CLI)                           │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │           Chrome Browser Control                    │      │
│  │  - Navigate pages                                   │      │
│  │  - Click elements                                   │      │
│  │  - Read DOM state                                   │      │
│  │  - Access console logs                              │      │
│  │  - Record interactions                              │      │
│  └────────────────────┬───────────────────────────────┘      │
│                       │                                      │
│                       │ Native Messaging API                 │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │  Claude in Chrome Extension │
           │  (v1.0.36+)                │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │     Google Chrome Browser   │
           │  - Tabs & Pages             │
           │  - DOM Interactions         │
           │  - Login Sessions           │
           └─────────────────────────────┘
```

### 3.2 Key Features

| Feature | Description | Use Case |
|---------|-------------|----------|
| **Shared Login State** | Uses existing Chrome sessions | No re-authentication for Google Docs, Gmail, Notion |
| **Manual Override** | Pauses for CAPTCHAs/login pages | Human handles blockers |
| **New Tab Isolation** | Opens new tabs for automation | Doesn't interfere with existing tabs |
| **Visible Execution** | Requires visible browser window | Maintains login state (no headless mode) |

### 3.3 Browser Automation Capabilities

**Core Actions:**
- **Navigation**: Go to URLs, manage tabs, handle page loads
- **Interaction**: Click elements, type text, scroll, submit forms
- **Reading**: Extract page content, DOM state, console logs, network requests
- **Recording**: Capture interactions as GIF files
- **Window Management**: Resize browser window, manage multiple tabs

**Example Use Cases:**

```bash
# Test local web app
claude --chrome
> "Go to localhost:3000, try submitting the form with invalid data,
   and check if the error messages appear correctly"

# Debug with console logs
> "Open the dashboard page and check the console for any errors
   when the page loads"

# Automate form filling
> "I have a spreadsheet of customer contacts in contacts.csv. For each row,
   go to our CRM at crm.example.com, click 'Add Contact', and fill in the
   name, email, and phone fields"

# Record demo GIF
> "Record a GIF showing how to complete the checkout flow, from adding
   an item to the cart through to the confirmation page"
```

### 3.4 Prerequisites & Limitations

**Prerequisites:**
- Google Chrome browser (not Brave, Arc, or other Chromium variants)
- Claude in Chrome extension (v1.0.36+)
- Claude Code CLI (v2.0.73+)
- Paid Claude plan (Pro, Team, or Enterprise)

**Limitations:**
- **No WSL support** (Windows Subsystem for Linux)
- **Beta status** (may have stability issues)
- **Chrome-only** (not cross-browser)

### 3.5 Comparison: Chrome Pairing vs Traditional Automation

| Aspect | Chrome Pairing | Headless Browsers | API-Only |
|--------|---------------|-------------------|----------|
| **Login Sessions** | ✅ Uses real sessions | ❌ Must handle separately | ❌ No browser state |
| **JavaScript Apps** | ✅ Seamless | ⚠️ May need waits | ❌ Can't interact |
| **Visual Verification** | ✅ GIF recording | ⚠️ Screenshot only | ❌ No visuals |
| **Console/Network** | ✅ Real-time access | ✅ Available | ❌ Not accessible |
| **CAPTCHA/Auth** | ✅ Manual override | ❌ Blockers | ❌ Not applicable |

**Strategic Insight:** Chrome pairing solves the "authenticated web workflows" problem that traditional automation tools struggle with. This is critical for business process automation.

---

## 4. Claude-Loop's Current Integration Model

### 4.1 Overview

Claude-loop's integration capabilities are **minimal and implicit**, not standardized:

```
┌──────────────────────────────────────────────────────────────┐
│                     claude-loop.sh                            │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │         Story Execution (Claude Code CLI)          │      │
│  │  - read_file                                       │      │
│  │  - write_file                                      │      │
│  │  - run_bash                                        │      │
│  │  - git_command                                     │      │
│  └────────────────────┬───────────────────────────────┘      │
│                       │                                      │
│                       │ No standardized connector layer      │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   Ad-hoc Bash Commands      │
           │  - curl (HTTP calls)        │
           │  - jq (JSON parsing)        │
           │  - git (version control)    │
           │  - npm/pip (package mgmt)   │
           └─────────────────────────────┘
```

### 4.2 Current Integration Points

| Type | Mechanism | Reliability | Discoverability |
|------|-----------|-------------|-----------------|
| **File System** | read_file, write_file | ✅ High | ✅ Documented tools |
| **Git** | git_command | ✅ High | ✅ Documented tool |
| **CLI Tools** | run_bash (curl, jq, etc.) | ⚠️ Variable | ❌ Implicit |
| **APIs** | run_bash + curl | ⚠️ Variable | ❌ No standard |
| **Databases** | run_bash + psql/mongo | ⚠️ Variable | ❌ No standard |
| **External Systems** | run_bash + custom scripts | ⚠️ Variable | ❌ No standard |

### 4.3 Agent-Based Specialization

Claude-loop's current approach to "integration" is through **domain-specific agents**:

**Example: `agents/backend-architect/`**
- Deep expertise in backend patterns
- No actual connection to external systems
- Guidance only, not executable connectors

**Agents Directory from README:**
- 34 agents total (5 core, 18 specialists, 11 domain-specific)
- Examples: code-reviewer, security-auditor, test-runner, typescript-specialist
- **Zero integration agents** for external systems

### 4.4 Multi-LLM Support (v0.9)

Claude-loop recently added **multi-LLM support**, but this is focused on **model diversity**, not external system integration:

```python
# lib/llm_provider.py - Provider abstraction
# lib/review_panel.py - Multi-model review
# lib/vision_analyzer.py - Vision analysis
```

**What it does:**
- Query multiple LLMs for code review
- Use vision models for image analysis
- Route reasoning tasks to specialized models

**What it doesn't do:**
- Connect to external databases
- Integrate with third-party APIs
- Access external data sources

### 4.5 Invisible Intelligence (v0.8)

The "Invisible Intelligence" system (v0.8) added **automatic complexity detection** and **agent selection**, but still no external integration layer:

```bash
# Complexity detection → agent selection
claude-loop.sh "Add user authentication with OAuth"
# → Detects complexity → Selects agents → Executes stories
```

**Still missing:** Ability to connect to external OAuth providers, databases, or APIs in a standardized way.

### 4.6 Current External Integration Pattern

When claude-loop needs external data, it relies on **bash commands**:

```bash
# Example: Query GitHub API
run_bash "curl -H 'Authorization: token $GITHUB_TOKEN' https://api.github.com/user"

# Example: Query database
run_bash "psql -U user -d mydb -c 'SELECT * FROM users'"

# Example: Call third-party API
run_bash "curl -X POST https://api.stripe.com/v1/charges -u sk_test_..."
```

**Problems with this approach:**

| Issue | Impact |
|-------|--------|
| **No schema validation** | Errors discovered at runtime |
| **No authentication management** | Credentials scattered in bash commands |
| **No rate limiting** | Risk of API throttling |
| **No retry logic** | Transient failures break stories |
| **No discoverability** | Can't browse available integrations |
| **No type safety** | JSON parsing errors common |

---

## 5. Gap Analysis

### 5.1 Missing Capabilities in Claude-Loop

| Capability | Cowork/Claude Code | Claude-Loop | Gap Severity |
|------------|-------------------|-------------|--------------|
| **MCP Server Support** | ✅ Full support | ❌ None | 🔴 **CRITICAL** |
| **Connector Directory** | ✅ Central directory | ❌ None | 🔴 **HIGH** |
| **Browser Automation** | ✅ Chrome pairing | ❌ None | 🟡 **MEDIUM** |
| **OAuth Management** | ✅ Per-connector | ❌ Manual in bash | 🔴 **HIGH** |
| **Resource @Mentions** | ✅ Unified interface | ❌ No equivalent | 🟡 **MEDIUM** |
| **External API Standards** | ✅ MCP protocol | ❌ Ad-hoc curl | 🔴 **HIGH** |
| **Database Connectors** | ✅ Via MCP servers | ❌ Direct psql/mongo | 🟡 **MEDIUM** |
| **Third-Party Integration** | ✅ 50+ connectors | ❌ Custom scripts | 🔴 **HIGH** |

### 5.2 Strategic Gap: No Platform Play

**Cowork's Advantage:** By adopting MCP and building a connector ecosystem, Anthropic is creating a **platform** where:
- Third-party developers extend capabilities
- New domains unlock new markets (e.g., healthcare)
- Network effects increase value (more connectors → more users → more connectors)

**Claude-Loop's Position:** Currently a **standalone tool** with no extensibility mechanism:
- Users can't add custom integrations easily
- No ecosystem of third-party extensions
- Limited to what bash commands can do

**Strategic Implication:** Claude-loop risks becoming a "closed system" while Cowork builds an open platform.

### 5.3 Opportunity: MCP Adoption

**Key Insight:** MCP is an **open protocol**, not proprietary to Anthropic. Claude-loop can adopt MCP and benefit from:

1. **Existing MCP Server Ecosystem**: 50+ connectors already built
2. **Standard Protocol**: No need to invent our own
3. **Community Development**: Third parties can extend claude-loop
4. **Claude Code Compatibility**: Share MCP servers with Claude Code users

**Examples of MCP Servers Available Today:**
- **GitHub** - Repository access, issue tracking
- **Slack** - Message sending, channel management
- **Notion** - Database queries, page creation
- **Postgres/MySQL** - Database queries
- **Google Drive** - File access
- **Jira** - Issue tracking, sprint management
- **Confluence** - Documentation access
- **Stripe** - Payment processing
- **AWS** - Cloud resource management

### 5.4 Prioritized Gaps

#### **P0 (Critical, Implement First)**

1. **MCP Server Configuration**
   - Read MCP config from `~/.claude.json` (standard location)
   - Support stdio and HTTP transports
   - Environment variable management for secrets

2. **MCP Tool Invocation**
   - Expose MCP tools as callable functions in stories
   - Track token usage from MCP tool outputs
   - Handle errors gracefully (retry logic, fallbacks)

3. **Resource Management**
   - Support @mention syntax for external resources
   - Cache resource metadata to reduce API calls
   - Implement token limits (warning at 10k, max 25k)

#### **P1 (High Priority, Core Functionality)**

4. **Connector Discovery**
   - List available MCP servers from config
   - Show available tools per server
   - Display example usage for each tool

5. **Authentication Management**
   - Secure credential storage (not in PRD files)
   - OAuth flow support (where applicable)
   - Environment variable templating (`${VAR_NAME}`)

6. **Integration Testing**
   - Test MCP server connectivity before story execution
   - Validate credentials during startup
   - Report integration health in dashboard

#### **P2 (Medium Priority, Enhanced Experience)**

7. **Browser Automation Support**
   - Detect if Claude in Chrome extension is available
   - Enable `--chrome` flag for browser tasks
   - Document browser automation patterns in AGENTS.md

8. **Connector Recommendations**
   - Analyze story descriptions for integration needs
   - Suggest relevant MCP servers (e.g., "needs database" → suggest postgres MCP)
   - Auto-configure common connectors (GitHub, Slack, Notion)

9. **Integration Metrics**
   - Track API calls per story
   - Monitor rate limits and throttling
   - Report cost per external API call

#### **P3 (Low Priority, Nice-to-Have)**

10. **Custom MCP Server Generator**
    - Scaffold new MCP servers from templates
    - Support common patterns (REST API wrapper, database connector)
    - Auto-generate from OpenAPI specs

### 5.5 Comparison Matrix

| Feature | Cowork/Claude Code | Claude-Loop (Current) | Claude-Loop (Proposed) |
|---------|-------------------|----------------------|------------------------|
| **External API Access** | ✅ MCP servers | ⚠️ Bash + curl | ✅ MCP servers |
| **Database Queries** | ✅ MCP servers | ⚠️ Direct psql/mongo | ✅ MCP servers |
| **OAuth Management** | ✅ Per-connector | ❌ Manual | ✅ Per-connector |
| **Browser Automation** | ✅ Chrome pairing | ❌ None | ✅ Chrome pairing |
| **Credential Security** | ✅ Encrypted storage | ⚠️ ENV vars | ✅ Encrypted storage |
| **Rate Limiting** | ✅ Built-in | ❌ Manual | ✅ Built-in |
| **Retry Logic** | ✅ Automatic | ❌ Manual | ✅ Automatic |
| **Connector Discovery** | ✅ Directory | ❌ None | ✅ CLI command |
| **Third-Party Extensions** | ✅ MCP ecosystem | ❌ None | ✅ MCP ecosystem |
| **Resource @Mentions** | ✅ Unified interface | ❌ None | ✅ Unified interface |

---

## 6. MCP-Compatible Architecture Proposal

### 6.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            claude-loop.sh                                 │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Story Orchestrator                            │    │
│  │  - Parse PRD                                                     │    │
│  │  - Execute stories sequentially                                 │    │
│  │  - Track progress                                               │    │
│  └────────────────────┬─────────────────────────────────────────────┘    │
│                       │                                                  │
│                       ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │            MCP Integration Layer (NEW)                          │    │
│  │  ┌────────────────────────────────────────────────────────┐    │    │
│  │  │ lib/mcp-manager.py                                     │    │    │
│  │  │  - Load ~/.claude.json config                          │    │    │
│  │  │  - Connect to MCP servers (stdio, HTTP, SSE)          │    │    │
│  │  │  - Expose MCP tools to stories                         │    │    │
│  │  │  - Track token usage from tool outputs                 │    │    │
│  │  └────────────────────────────────────────────────────────┘    │    │
│  │  ┌────────────────────────────────────────────────────────┐    │    │
│  │  │ lib/resource-resolver.py                               │    │    │
│  │  │  - Parse @mention syntax                               │    │    │
│  │  │  - Fetch resources from MCP servers                    │    │    │
│  │  │  - Cache metadata to reduce API calls                  │    │    │
│  │  └────────────────────────────────────────────────────────┘    │    │
│  │  ┌────────────────────────────────────────────────────────┐    │    │
│  │  │ lib/credential-manager.py                              │    │    │
│  │  │  - Secure credential storage (keyring)                 │    │    │
│  │  │  - Environment variable templating                     │    │    │
│  │  │  - OAuth flow support (where applicable)               │    │    │
│  │  └────────────────────────────────────────────────────────┘    │    │
│  └────────────────────┬─────────────────────────────────────────────┘    │
│                       │                                                  │
│                       ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Claude Code CLI + Core Tools                        │    │
│  │  - read_file, write_file, run_bash, git_command                 │    │
│  │  - MCP tools (exposed via integration layer)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │
                                  ▼
         ┌────────────────────────────────────────────────────────┐
         │           MCP Servers (External)                        │
         │                                                         │
         │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
         │  │  GitHub  │  │  Notion  │  │ Postgres │             │
         │  │  Server  │  │  Server  │  │  Server  │             │
         │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
         │       │             │             │                   │
         └───────┼─────────────┼─────────────┼─────────────────────┘
                 │             │             │
                 ▼             ▼             ▼
         ┌──────────┐  ┌──────────┐  ┌──────────┐
         │  GitHub  │  │  Notion  │  │ Postgres │
         │   API    │  │   API    │  │Database  │
         └──────────┘  └──────────┘  └──────────┘
```

### 6.2 Core Components

#### **6.2.1 lib/mcp-manager.py**

**Responsibilities:**
- Load MCP server configuration from `~/.claude.json`
- Establish connections to MCP servers (stdio, HTTP, SSE transports)
- Expose MCP tools to story execution context
- Track token usage from MCP tool outputs
- Implement token limits (warning at 10k, max 25k per tool call)

**API:**
```python
from lib.mcp_manager import MCPManager

# Initialize
mcp = MCPManager(config_path="~/.claude.json")

# List available servers
servers = mcp.list_servers()
# [{'name': 'github', 'status': 'connected', 'tools': ['get_repo', 'create_issue']}]

# Call MCP tool
result = mcp.call_tool("github", "get_repo", {"owner": "user", "repo": "repo"})
# {'content': {...}, 'tokens': 1234}

# Get token usage
usage = mcp.get_token_usage()
# {'github': 5432, 'notion': 2100}
```

**Configuration Example (`~/.claude.json`):**
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "postgres": {
      "transport": "http",
      "url": "https://mcp.example.com/postgres",
      "headers": {
        "Authorization": "Bearer ${DB_API_KEY}"
      }
    }
  }
}
```

#### **6.2.2 lib/resource-resolver.py**

**Responsibilities:**
- Parse `@mention` syntax in story descriptions and acceptance criteria
- Fetch resources from MCP servers
- Cache metadata to reduce API calls
- Return resource content for inclusion in context

**API:**
```python
from lib.resource_resolver import ResourceResolver

# Initialize
resolver = ResourceResolver(mcp_manager)

# Parse @mentions from text
text = "Review @github-issues and update @notion-roadmap"
mentions = resolver.parse_mentions(text)
# [{'source': 'github', 'resource': 'issues'}, {'source': 'notion', 'resource': 'roadmap'}]

# Resolve mentions to actual content
resolved = resolver.resolve_mentions(mentions)
# [{'mention': '@github-issues', 'content': '[Issue #123, Issue #124]', 'tokens': 500}]

# Get cached resources (avoid re-fetching)
cached = resolver.get_cache_status()
# {'github-issues': {'cached': True, 'expires': '2026-01-13T10:00:00Z'}}
```

#### **6.2.3 lib/credential-manager.py**

**Responsibilities:**
- Secure credential storage using OS keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- Environment variable templating (`${VAR_NAME}` → actual value)
- OAuth flow support for connectors requiring it
- Credential validation before story execution

**API:**
```python
from lib.credential_manager import CredentialManager

# Initialize
creds = CredentialManager()

# Store credential securely
creds.set_credential("github", "token", "ghp_...")

# Retrieve credential
token = creds.get_credential("github", "token")
# "ghp_..."

# Validate all credentials for a PRD
missing = creds.validate_prd_credentials(prd)
# ['notion_token', 'slack_webhook'] - list of missing credentials

# Template environment variables
config = {"url": "https://api.github.com", "token": "${GITHUB_TOKEN}"}
resolved = creds.resolve_template(config)
# {"url": "https://api.github.com", "token": "ghp_..."}
```

### 6.3 Story-Level Integration

Stories can now specify required MCP servers in `fileScope` (extended schema):

**Extended PRD Schema:**
```json
{
  "id": "US-001",
  "title": "Sync GitHub Issues to Notion",
  "fileScope": [
    "lib/github_sync.py",
    "lib/notion_client.py"
  ],
  "integrations": [
    {
      "server": "github",
      "tools": ["list_issues", "get_issue"],
      "required": true
    },
    {
      "server": "notion",
      "tools": ["create_page", "update_database"],
      "required": true
    }
  ]
}
```

**Pre-Story Validation:**
Before executing a story, claude-loop validates:
1. All required MCP servers are configured
2. All required credentials are available
3. MCP servers are reachable (test connection)
4. Required tools are available on servers

If validation fails, the story is **blocked** with a clear error message:

```
❌ Story US-001 blocked: Missing MCP servers
   - github: Not configured. Run `claude mcp add github`
   - notion: Credentials missing. Set NOTION_API_KEY
```

### 6.4 Integration with Agent System

**Current Agent System:**
- 34 agents providing domain-specific guidance
- No executable integration capabilities

**Proposed Enhancement:**
Extend agents to **recommend MCP servers** based on story context.

**Example: Backend Architect Agent**

**Before:**
```markdown
For database operations, use a proper ORM (Prisma, TypeORM, Sequelize)
```

**After:**
```markdown
For database operations:
1. Use a proper ORM (Prisma, TypeORM, Sequelize)
2. Consider using MCP postgres connector for direct queries:
   - Add server: `claude mcp add postgres`
   - Query in story: `mcp.call_tool("postgres", "query", {"sql": "SELECT * FROM users"})`
```

**Implementation:**
- Add `recommendedIntegrations` field to agent definitions
- Agent selection automatically suggests MCP servers for the story
- Display in story planning phase: "This story may benefit from: [github, notion]"

### 6.5 Browser Automation Integration

**Proposed `--chrome` Flag:**

```bash
# Enable Chrome pairing for browser automation tasks
./claude-loop.sh --chrome

# Specify Chrome profile for login sessions
./claude-loop.sh --chrome --profile "Work"
```

**Story Declaration:**
```json
{
  "id": "US-005",
  "title": "Test Checkout Flow E2E",
  "requiresBrowser": true,
  "browserTasks": [
    "Navigate to localhost:3000/checkout",
    "Fill shipping address form",
    "Verify order confirmation appears"
  ]
}
```

**Implementation:**
- Check if Claude in Chrome extension is installed (`claude --chrome` command)
- If not available, block story with installation instructions
- Pass `--chrome` flag to Claude Code when executing browser-required stories
- Capture GIF recordings for visual regression testing

### 6.6 Dashboard Integration

**New Dashboard Section: "Integrations"**

```
┌──────────────────────────────────────────────────────────────┐
│                    claude-loop Dashboard                      │
│                                                               │
│  Project: user-sync-system                                    │
│  Status: Running                                              │
│                                                               │
│  Integrations:                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ MCP Servers                                            │  │
│  │  ✅ github        (5 tools, 12,345 tokens)            │  │
│  │  ✅ notion        (8 tools, 8,901 tokens)             │  │
│  │  ✅ postgres      (3 tools, 2,456 tokens)             │  │
│  │  ⚠️  slack         (Not configured)                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Recent API Calls:                                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 10:23:45  github.list_issues      ✅ 234 tokens       │  │
│  │ 10:24:12  notion.create_page      ✅ 567 tokens       │  │
│  │ 10:25:33  postgres.query          ✅ 123 tokens       │  │
│  │ 10:26:01  github.get_issue        ❌ Rate limited     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**Implementation:**
- Extend `lib/monitoring.sh` to track MCP tool calls
- Add `mcp_tools_used`, `mcp_tokens`, `mcp_errors` to metrics
- Display integration health in dashboard
- Alert on rate limits or authentication failures

---

## 7. Implementation Roadmap

### Phase 1: Foundation (4-6 weeks)

**Goal:** Basic MCP support for stdio servers (local tools)

**Stories:**

| ID | Title | Effort | Priority |
|----|-------|--------|----------|
| **INT-001** | MCP Manager - Config Loading | 5 days | P0 |
| **INT-002** | MCP Manager - Stdio Transport | 5 days | P0 |
| **INT-003** | MCP Manager - Tool Invocation | 5 days | P0 |
| **INT-004** | Resource Resolver - @Mention Parsing | 3 days | P1 |
| **INT-005** | Resource Resolver - Resource Fetching | 3 days | P1 |
| **INT-006** | Credential Manager - Basic Storage | 5 days | P0 |
| **INT-007** | Pre-Story Integration Validation | 3 days | P1 |
| **INT-008** | Integration Tests - GitHub MCP Server | 2 days | P1 |

**Acceptance Criteria:**
- Read MCP config from `~/.claude.json`
- Connect to stdio-based MCP servers (e.g., GitHub)
- Call MCP tools from stories
- Track token usage from tool outputs
- Validate MCP servers before story execution
- Pass 10+ integration tests with GitHub MCP server

**Deliverables:**
- `lib/mcp_manager.py` (200-300 lines)
- `lib/resource_resolver.py` (150-200 lines)
- `lib/credential_manager.py` (100-150 lines)
- Documentation: `docs/guides/mcp-integration.md`
- Tests: `tests/test_mcp_integration.py`

### Phase 2: HTTP & Advanced Features (4-6 weeks)

**Goal:** HTTP transport, OAuth, browser automation

**Stories:**

| ID | Title | Effort | Priority |
|----|-------|--------|----------|
| **INT-009** | MCP Manager - HTTP Transport | 5 days | P0 |
| **INT-010** | MCP Manager - SSE Transport | 3 days | P1 |
| **INT-011** | Credential Manager - OAuth Flows | 8 days | P1 |
| **INT-012** | Browser Automation - Chrome Detection | 2 days | P2 |
| **INT-013** | Browser Automation - Story Integration | 5 days | P2 |
| **INT-014** | Resource Resolver - Caching Layer | 5 days | P1 |
| **INT-015** | Dashboard - Integration Metrics | 3 days | P2 |
| **INT-016** | Agent System - Integration Recommendations | 5 days | P2 |

**Acceptance Criteria:**
- Connect to HTTP-based MCP servers (remote APIs)
- Support SSE transport for real-time streams
- Handle OAuth authentication flows
- Detect Chrome extension availability
- Execute browser automation stories
- Cache resource metadata (60% cache hit rate)
- Display integration metrics in dashboard
- Agents recommend relevant MCP servers

**Deliverables:**
- HTTP/SSE transport support in `lib/mcp_manager.py`
- OAuth support in `lib/credential_manager.py`
- Browser automation in `lib/browser_integration.py`
- Dashboard integration in `dashboard/app.py`
- Agent integration recommendations in `lib/agent-registry.sh`

### Phase 3: Ecosystem & Polish (2-4 weeks)

**Goal:** Connector discovery, documentation, community enablement

**Stories:**

| ID | Title | Effort | Priority |
|----|-------|--------|----------|
| **INT-017** | Connector Discovery CLI | 3 days | P2 |
| **INT-018** | Auto-Configuration Wizard | 5 days | P3 |
| **INT-019** | MCP Server Generator (Template) | 5 days | P3 |
| **INT-020** | Integration Cookbook (Docs) | 3 days | P2 |
| **INT-021** | Rate Limiting & Retry Logic | 5 days | P1 |
| **INT-022** | Integration Health Monitoring | 3 days | P2 |

**Acceptance Criteria:**
- CLI command to list available MCP servers: `./claude-loop.sh --list-integrations`
- Auto-configuration wizard for common connectors (GitHub, Notion, Slack)
- Template for creating custom MCP servers
- Cookbook with 10+ integration examples
- Automatic retry on transient failures (3 retries, exponential backoff)
- Integration health dashboard with uptime metrics

**Deliverables:**
- `lib/connector_discovery.py`
- `lib/auto_config_wizard.py`
- `templates/mcp-server-template/`
- Documentation: `docs/guides/integration-cookbook.md`
- Health monitoring in `lib/integration_health.py`

### Timeline Summary

| Phase | Duration | Stories | Key Deliverables |
|-------|----------|---------|------------------|
| **Phase 1** | 4-6 weeks | 8 stories | MCP manager, resource resolver, credential manager |
| **Phase 2** | 4-6 weeks | 8 stories | HTTP/OAuth, browser automation, dashboard |
| **Phase 3** | 2-4 weeks | 6 stories | Discovery CLI, auto-config, cookbook |
| **Total** | **10-16 weeks** | **22 stories** | Full MCP integration, browser automation, ecosystem |

### Resource Requirements

| Role | Phase 1 | Phase 2 | Phase 3 | Total |
|------|---------|---------|---------|-------|
| **Backend Engineer** | 4-6 weeks | 4-6 weeks | 2-4 weeks | 10-16 weeks |
| **DevOps Engineer** | - | 2 weeks | 1 week | 3 weeks |
| **Technical Writer** | - | - | 2 weeks | 2 weeks |

**Estimated Cost:** $50k - $80k (assuming $150/hour blended rate)

---

## 8. Conclusion

### 8.1 Key Findings

1. **Cowork's Integration Model is MCP-Based**: All connectors are built on the open Model Context Protocol, enabling a plug-and-play ecosystem.

2. **Claude-Loop Has Zero Standardized Integration**: Current approach relies on ad-hoc bash commands (curl, jq, etc.) with no schema validation, authentication management, or retry logic.

3. **MCP is Open and Adoptable**: Claude-loop can adopt MCP without vendor lock-in, benefiting from the existing ecosystem of 50+ connectors.

4. **Browser Automation is a Differentiator**: Chrome pairing solves authenticated web workflows that traditional automation tools struggle with.

5. **Strategic Gap: No Platform Play**: Cowork is building a platform with network effects (third-party connectors). Claude-loop is currently a standalone tool.

### 8.2 Strategic Recommendations

#### **Immediate Actions (Next 2 Weeks)**

1. **Adopt MCP as Integration Standard**
   - Decision: Make MCP the official integration protocol for claude-loop
   - Rationale: Open standard, existing ecosystem, Claude Code compatibility

2. **Prioritize Phase 1 Stories**
   - Focus: Basic MCP support for stdio servers (GitHub, Notion, etc.)
   - Impact: Unblocks external system integration for 80% of use cases

3. **Document Integration Vision**
   - Create RFC: "RFC-003: MCP Integration Architecture"
   - Socialize with community for feedback

#### **Short-Term Goals (3 Months)**

4. **Complete Phase 1 & Phase 2**
   - Deliverables: MCP manager, HTTP transport, browser automation
   - Target: 10+ MCP servers supported (GitHub, Notion, Slack, Postgres, etc.)

5. **Integration Cookbook**
   - Create 10+ integration examples (GitHub sync, Slack notifications, database queries)
   - Lower barrier to entry for users

6. **Dashboard Integration Metrics**
   - Display MCP server health, API call metrics, token usage
   - Alert on rate limits or authentication failures

#### **Long-Term Vision (12 Months)**

7. **Build Connector Ecosystem**
   - Encourage third-party MCP server development
   - Create showcase directory of claude-loop-compatible connectors

8. **Vertical-Specific Integrations**
   - Healthcare: FHIR, HL7, Epic, Cerner connectors
   - Finance: Plaid, Stripe, QuickBooks connectors
   - E-commerce: Shopify, WooCommerce, Magento connectors

9. **MCP Server Generator**
   - Auto-generate MCP servers from OpenAPI specs
   - Scaffold custom connectors from templates

### 8.3 Competitive Positioning

**After MCP Integration:**

| Capability | Cowork | Claude-Loop (Proposed) | Advantage |
|------------|--------|------------------------|-----------|
| **External Integration** | ✅ MCP servers | ✅ MCP servers | 🟰 **Parity** |
| **Browser Automation** | ✅ Chrome pairing | ✅ Chrome pairing | 🟰 **Parity** |
| **Autonomous Feature Implementation** | ❌ Task-level | ✅ Multi-story PRD | 🟢 **Claude-Loop** |
| **Quality Gates** | ⚠️ Self-checking | ✅ Automated tests/lint | 🟢 **Claude-Loop** |
| **Persistent Memory** | ❌ Transient | ✅ Stratified memory | 🟢 **Claude-Loop** |
| **Multi-Day Projects** | ⚠️ Limited | ✅ Optimized | 🟢 **Claude-Loop** |
| **Self-Improvement** | ❌ None | ✅ Learns from failures | 🟢 **Claude-Loop** |
| **User Audience** | 🟢 **Non-technical** | ⚠️ Developers | 🟢 **Cowork** |

**Strategic Positioning:**
- **Cowork**: "AI colleague for business tasks" (document creation, file work, quick automations)
- **Claude-Loop + MCP**: "Autonomous feature implementation platform with external system orchestration"

**Competitive Moat:**
- Cowork's moat: Simplicity, no-code experience, task-level delegation
- Claude-Loop's moat: Multi-story projects, quality gates, persistent memory, self-improvement

**Market Segmentation:**
- Cowork: Business users, non-developers, quick tasks (<1 hour)
- Claude-Loop: Developers, complex features, multi-day projects

### 8.4 Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **MCP Ecosystem Immaturity** | Medium | Medium | Contribute to MCP development, build fallback stdio support |
| **Authentication Complexity** | High | Medium | Start with ENV vars, OAuth in Phase 2 |
| **Performance Overhead** | Low | Low | Cache resources aggressively, set token limits |
| **User Confusion** | Medium | Medium | Clear documentation, auto-configuration wizard |
| **Credential Security** | Medium | High | Use OS keyring, never store in PRD files |

### 8.5 Success Metrics

**Phase 1 Success Criteria (3 Months):**
- ✅ 5+ MCP servers integrated (GitHub, Notion, Slack, Postgres, MySQL)
- ✅ 80% of integration tests passing
- ✅ 10+ community PRDs using MCP integrations
- ✅ Zero credential leaks or security incidents

**Phase 2 Success Criteria (6 Months):**
- ✅ HTTP/OAuth support for 20+ MCP servers
- ✅ Browser automation for 5+ web workflow PRDs
- ✅ Integration metrics visible in dashboard
- ✅ 50+ community PRDs using integrations

**Phase 3 Success Criteria (12 Months):**
- ✅ 50+ MCP servers in ecosystem
- ✅ Auto-configuration wizard for top 10 connectors
- ✅ 10+ user-contributed MCP servers
- ✅ Integration cookbook with 25+ examples

---

## Sources

- [Claude Connectors Directory](https://claude.com/connectors)
- [Introducing Cowork | Claude Blog](https://claude.com/blog/cowork-research-preview)
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Claude Code Chrome Integration](https://code.claude.com/docs/en/chrome)
- [Model Context Protocol Official Site](https://modelcontextprotocol.io/)
- [Anthropic MCP Announcement](https://www.anthropic.com/news/model-context-protocol)
- [Claude for Healthcare Launch](https://fortune.com/2026/01/11/anthropic-unveils-claude-for-healthcare-and-expands-life-science-features-partners-with-healthex-to-let-users-connect-medical-records/)
- [VentureBeat: Cowork Launch](https://venturebeat.com/technology/anthropic-launches-cowork-a-claude-desktop-agent-that-works-in-your-files-no)
- [Claude AI Connectors Review 2026](https://elephas.app/blog/claude-connectors-review)

---

**End of Analysis**
