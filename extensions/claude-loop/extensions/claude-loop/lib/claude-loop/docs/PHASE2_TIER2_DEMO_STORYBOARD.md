# Phase 2 Tier 2 Demo Storyboard

> Demo Script for MCP Integration, Multi-Provider LLM, and Bounded Delegation
> Duration: 10-12 minutes
> Target Audience: Developers, DevOps engineers, AI/ML practitioners

---

## Demo Overview

This demo showcases three major Phase 2 Tier 2 features that enable claude-loop to:
1. Access external tools via MCP (Model Context Protocol)
2. Optimize costs with multi-provider LLM routing
3. Handle complex tasks with bounded hierarchical delegation

**Key Value Propositions**:
- 30-50% cost reduction via intelligent provider selection
- Extensibility through MCP ecosystem (filesystem, databases, APIs)
- Complex task handling with strict safety guarantees (depth=2, context=100k)

---

## Demo Setup (Pre-Demo)

### Prerequisites

```bash
# Install MCP filesystem server
npm install -g @modelcontextprotocol/server-filesystem

# Configure API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."

# Start MCP server (background)
npx @modelcontextprotocol/server-filesystem /path/to/demo-codebase &

# Copy example configurations
cp .claude-loop/mcp-config.example.json .claude-loop/mcp-config.json
cp lib/llm_providers.example.yaml lib/llm_providers.yaml

# Prepare demo PRD
cp prds/examples/mcp-usage-example.json prd-demo.json
```

### Demo Repository

Clone demo repository with intentional complexity:
```bash
git clone https://github.com/demo/microservices-app demo-codebase
cd demo-codebase
# 10 microservices, 5k+ files, realistic codebase
```

---

## Act 1: Problem Statement (1 minute)

### Scene 1: The Challenges

**Narrator**: "Traditional autonomous coding agents face three major challenges..."

**Visual**: Split screen showing three pain points:

1. **Limited Tool Access** (Left third)
   - Screen recording: Agent tries to query database, can't access it
   - Text overlay: "Agents are isolated from external systems"
   - Red X icon

2. **High API Costs** (Middle third)
   - Cost dashboard showing expensive Opus-only execution
   - Text overlay: "$150 for simple refactoring tasks"
   - Red X icon

3. **Task Complexity Limits** (Right third)
   - Agent failing on complex multi-faceted feature
   - Text overlay: "Can't break down architectural changes"
   - Red X icon

**Narrator**: "Phase 2 Tier 2 solves all three."

---

## Act 2: Feature 1 - MCP Integration (3 minutes)

### Scene 2: Introducing MCP

**Visual**: Transition to terminal with MCP architecture diagram overlay

**Narrator**: "MCP (Model Context Protocol) lets agents access external tools safely."

**Terminal Commands** (with overlays explaining each):

```bash
# Show MCP configuration
cat .claude-loop/mcp-config.json
```

**Visual Overlay**: Highlight configuration structure:
- Server endpoints
- Tool whitelists (read-only by default)
- Security settings

### Scene 3: MCP in Action

**Narrator**: "Let's analyze a codebase using MCP filesystem tools."

**PRD Snippet** (show in editor):
```json
{
  "id": "US-001",
  "title": "Analyze authentication service dependencies",
  "description": "Use MCP to read service files and identify dependencies"
}
```

**Terminal**: Start execution with MCP enabled
```bash
./claude-loop.sh --enable-mcp prd-demo.json
```

**Visual**: Split screen:
- **Left**: Terminal output scrolling (show MCP calls being made)
- **Right**: Live visualization of MCP tool calls

**Annotations** (appear as MCP calls execute):
1. `[use-mcp:filesystem/list_directory:{"path": "services/auth"}]`
   - Overlay: "Listing files in auth service"
2. `[use-mcp:filesystem/read_file:{"path": "services/auth/config.yaml"}]`
   - Overlay: "Reading configuration (read-only)"
3. Result appears in context
   - Overlay: "MCP response injected into agent context"

**Terminal**: Show MCP call log
```bash
tail -f .claude-loop/logs/mcp_calls.jsonl
```

**Visual**: JSON entries streaming, highlight:
- Tool used: `filesystem/read_file`
- Latency: `234ms`
- Success: `true`

**Narrator**: "MCP calls are logged, validated, and restricted to whitelisted tools."

### Scene 4: Security Model

**Visual**: Security diagram overlay

**Narrator**: "MCP's security model protects your system."

**Bullet Points** (animated appearance):
- ✓ Whitelist-only execution
- ✓ Read-only default
- ✓ Schema validation
- ✓ Audit logging
- ✓ Timeout protection (5s)

---

## Act 3: Feature 2 - Multi-Provider LLM (3 minutes)

### Scene 5: The Cost Problem

**Visual**: Cost comparison chart

**Narrator**: "Using only Opus for all tasks is expensive."

**Chart** (animated):
- **Before (Phase 1)**: All tasks → Opus ($15/M input)
  - Simple refactoring: $1.50
  - Medium feature: $3.00
  - Complex architecture: $5.00
  - **Total: $9.50**

- **After (Phase 2.2)**: Intelligent routing
  - Simple → Haiku ($0.25/M): $0.15 💰
  - Medium → Sonnet ($3/M): $1.20 💰
  - Complex → Opus ($15/M): $4.50
  - **Total: $5.85** (38% savings)

### Scene 6: Provider Selection in Action

**Terminal**: Show provider configuration
```bash
cat lib/llm_providers.yaml
```

**Visual**: Highlight provider capabilities and costs

**Terminal**: Run with multi-provider enabled
```bash
./claude-loop.sh --enable-multi-provider prd-demo.json
```

**Visual**: Real-time provider selection overlay

**Animation** (as each story executes):
1. **Story US-001** (Simple: Fix typo)
   - Complexity score: 2
   - Selected provider: **Haiku** (cheapest)
   - Cost: $0.12
   - Overlay: "Simple task → cheap model"

2. **Story US-002** (Medium: Add validation)
   - Complexity score: 4
   - Selected provider: **Sonnet** (balanced)
   - Cost: $1.15
   - Overlay: "Medium task → mid-tier model"

3. **Story US-003** (Complex: Refactor auth)
   - Complexity score: 7
   - Selected provider: **Opus** (powerful)
   - Cost: $4.50
   - Overlay: "Complex task → powerful model"

**Terminal**: Show cost report
```bash
./claude-loop.sh --cost-report
```

**Visual**: Cost breakdown table appears:

| Story | Complexity | Provider | Cost | Phase 1 Cost | Savings |
|-------|------------|----------|------|--------------|---------|
| US-001 | 2 | Haiku | $0.12 | $1.50 | 92% |
| US-002 | 4 | Sonnet | $1.15 | $3.00 | 62% |
| US-003 | 7 | Opus | $4.50 | $5.00 | 10% |
| **Total** | - | - | **$5.77** | **$9.50** | **39%** |

### Scene 7: Fallback Chain

**Narrator**: "Provider failures? No problem. Automatic fallback."

**Visual**: Fallback chain animation:
1. Primary provider (OpenAI) → Rate limit ❌
2. Automatic fallback to secondary (Google) → Success ✓
3. If all fail → Claude CLI (always available) ✓

**Terminal**: Show provider usage log
```bash
jq '.fallback_used' .claude-loop/logs/provider_usage.jsonl
```

**Output**: `true` for rate-limited iteration

---

## Act 4: Feature 3 - Bounded Delegation (3 minutes)

### Scene 8: Complex Task Breakdown

**Narrator**: "Some features are too complex for a single agent."

**Visual**: Show complex PRD story:
```json
{
  "id": "US-004",
  "title": "Implement user authentication system",
  "description": "Add JWT auth with login, signup, password reset, and email verification"
}
```

**Narrator**: "This requires: backend logic, frontend UI, email templates, and tests. Delegation breaks it down."

### Scene 9: Delegation in Action

**Terminal**: Enable delegation
```bash
./claude-loop.sh --enable-delegation prd-demo.json
```

**Visual**: Delegation flow animation

1. **Parent Agent** analyzes task
   - Overlay: "Parent identifies need for delegation"

2. **Delegation Requests** appear:
   ```
   [delegate:Implement JWT backend logic:3]
   [delegate:Create login/signup UI:2]
   [delegate:Add email templates:1]
   ```
   - Overlay: "3 subtasks identified"

3. **Validation** (animated checks):
   - ✓ Depth check: 0 + 1 = 1 < 2 (OK)
   - ✓ Context check: 45k < 100k (OK)
   - ✓ Cycle check: No cycles (OK)

4. **Parallel Execution** (split screen):
   - Left: Subtask 1 (Backend) in worktree A
   - Middle: Subtask 2 (UI) in worktree B
   - Right: Subtask 3 (Email) in worktree C
   - Progress bars for each

5. **Results Injection**:
   - Completed subtasks merge back to parent
   - Parent sees summary of all changes
   - Final integration and tests

**Terminal**: Show delegation tree
```bash
python3 lib/delegation_visualizer.py show
```

**Visual**: ASCII tree appears:
```
US-004 (Implement authentication)
├─ US-004-1 (JWT backend logic) ✓
├─ US-004-2 (Login/signup UI) ✓
└─ US-004-3 (Email templates) ✓
```

### Scene 10: Safety Guarantees

**Visual**: Safety limits diagram

**Narrator**: "Delegation is bounded to prevent runaway complexity."

**Animated Limits** (appear sequentially):
1. **Depth Limit**: MAX_DELEGATION_DEPTH=2
   - Visual: Tree showing parent → child → grandchild, then ❌ for further depth
2. **Context Limit**: MAX_CONTEXT_PER_AGENT=100k tokens
   - Visual: Token counter reaching 100k, then ❌
3. **Cycle Detection**: A→B→A blocked
   - Visual: Circular arrow with ❌ overlay
4. **Timeout**: 5 minutes per subtask
   - Visual: Timer reaching 5:00, then ❌

**Terminal**: Attempt to exceed depth limit
```bash
# Simulated: Depth 3 delegation attempt
ERROR: Delegation depth limit (2) exceeded. Cannot delegate further.
```

---

## Act 5: Integration Demo (2 minutes)

### Scene 11: All Features Together

**Narrator**: "Let's use all three features on a real task."

**PRD** (show in editor):
```json
{
  "id": "US-005",
  "title": "Optimize microservices performance",
  "description": "Use MCP to analyze service metrics, delegate optimization subtasks to different services, use multi-provider for cost efficiency"
}
```

**Terminal**: Run with all features enabled
```bash
./claude-loop.sh --enable-mcp --enable-multi-provider --enable-delegation prd-demo.json
```

**Visual**: Dashboard view (http://localhost:8080) showing:

1. **Story Status Grid** (top):
   - US-005 (in progress, yellow)
   - Subtasks appearing dynamically

2. **Real-Time Logs** (left):
   - MCP calls to query metrics
   - Provider selections (Haiku → Sonnet → Opus)
   - Delegation requests

3. **Cost Tracker** (right):
   - Running cost: $3.25
   - Budget: $10.00
   - Savings vs Phase 1: 45%

4. **Delegation Tree** (bottom):
   - Live tree visualization growing as subtasks spawn

**Narrator**: "All features working together seamlessly."

### Scene 12: Final Results

**Terminal**: Execution completes
```
✓ US-005 complete
✓ 3 subtasks delegated (parallel execution)
✓ 8 MCP calls (all successful)
✓ 4 providers used (Haiku, Sonnet, Opus, GPT-4o)
✓ Total cost: $3.42 (vs $7.50 Phase 1 - 54% savings)
✓ Execution time: 4m 32s (vs ~6m sequential)
```

**Visual**: Success animation with key metrics highlighted

---

## Act 6: Summary and Call to Action (1 minute)

### Scene 13: Recap

**Narrator**: "Phase 2 Tier 2 delivers three game-changing capabilities."

**Visual**: Three feature cards (animated entrance):

1. **MCP Integration**
   - Access 100+ community tools
   - Filesystem, databases, APIs, cloud services
   - Security: whitelist-only, read-only default

2. **Multi-Provider LLM**
   - 30-50% cost reduction
   - Intelligent routing (complexity-based)
   - 10+ providers (OpenAI, Google, DeepSeek, etc.)

3. **Bounded Delegation**
   - Handle complex features
   - Safe parallelization (strict limits)
   - 2x-3x throughput on eligible tasks

### Scene 14: Get Started

**Visual**: Terminal commands overlay

**Narrator**: "Get started in 3 commands:"

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure providers
cp lib/llm_providers.example.yaml lib/llm_providers.yaml
# Edit with your API keys

# 3. Run with Phase 2 Tier 2
./claude-loop.sh --enable-mcp --enable-multi-provider --enable-delegation prd.json
```

**Visual**: Documentation links appear:
- [MCP Integration Guide](docs/features/mcp-integration.md)
- [Multi-Provider Setup](docs/features/multi-provider-llm.md)
- [Delegation Best Practices](docs/features/bounded-delegation.md)
- [Migration Guide](docs/MIGRATION_TIER2.md)

**Narrator**: "Full documentation, examples, and support available."

**Final Frame**: claude-loop logo with tagline:
> "Autonomous coding with cost efficiency, extensibility, and safe complexity handling."

---

## Technical Notes for Video Production

### Recording Setup

**Software**:
- Screen recording: OBS Studio or Loom
- Terminal: iTerm2 with increased font size (18pt)
- Editor: VS Code with high-contrast theme
- Browser: Chrome for dashboard view

**Recording Tips**:
- Use `asciinema` for terminal recordings (easier editing)
- Record dashboard in separate takes (cleaner compositing)
- Pre-script all terminal commands (paste from file for consistency)
- Use `sleep 2` between commands for pacing

### Visual Effects

**Overlays**:
- Use green screen for annotations
- Highlight terminal output with colored boxes
- Animated arrows for data flow diagrams

**Animations**:
- Fade-in for bullet points (300ms delay between items)
- Slide-in for comparison tables
- Pulsing highlight for key metrics

**Text Styling**:
- Title: Roboto Bold 48pt
- Body: Roboto Regular 24pt
- Code: Fira Code 20pt
- Annotations: Roboto Italic 18pt

### Audio

**Narration Script**:
- Professional voice-over (clear, measured pace)
- Background music: Subtle tech/ambient (20% volume)
- Sound effects: Minimal (success chime, error buzz)

**Timing**:
- Total duration: 10-12 minutes
- Pause after each key point (2-3 seconds)
- Allow terminal output to scroll naturally (don't speed up)

---

## Alternate Demo Formats

### Quick Demo (5 minutes)

Focus on one feature per minute:
- Minute 1: Problem statement
- Minute 2: MCP showcase
- Minute 3: Multi-provider showcase
- Minute 4: Delegation showcase
- Minute 5: Combined demo + CTA

### Interactive Workshop (30 minutes)

Live coding session:
- Participants follow along with provided demo repo
- Configure MCP, providers, delegation step-by-step
- Run actual PRD with all features enabled
- Q&A at end

### Blog Post / Written Tutorial

Convert storyboard to written guide:
- Screenshots instead of video
- Step-by-step instructions
- Code snippets with explanations
- GIFs for key interactions (delegation tree, dashboard)

---

## Demo Assets Checklist

- [ ] Demo repository cloned and prepared
- [ ] MCP server installed and running
- [ ] API keys configured (Anthropic, OpenAI, Google)
- [ ] Example PRD files ready (`prd-demo.json`)
- [ ] Dashboard running at http://localhost:8080
- [ ] Terminal theme configured (high contrast, large font)
- [ ] Screen recording software tested
- [ ] Audio equipment tested
- [ ] Narration script printed
- [ ] Backup plan if API fails (use pre-recorded demo)

---

## Success Metrics

**Engagement**:
- Watch time >50%
- Click-through to documentation >10%
- GitHub stars increase >100 within 1 week

**Technical**:
- Demo completes without errors
- All features showcase successfully
- Cost savings visible (>30%)

**Audience Feedback**:
- Comments understand value propositions
- Questions focus on "how to get started" (not "what does it do")
- Requests for more advanced features (validation of complexity handling)

---

*This storyboard is maintained alongside Phase 2 Tier 2 feature development. Last updated: 2026-01-20.*
