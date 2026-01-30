# Execution Modes - Customizable Workflows

**Status**: ✅ Implemented (US-007)

**Impact**: Provides flexibility to customize claude-loop workflows based on team preferences and project needs

## Overview

The execution modes system allows you to configure how claude-loop operates, choosing between **interactive**, **autonomous**, or **hybrid** modes based on your workflow preferences.

## Execution Modes

### Interactive Mode

**Best for**: New projects, complex features, high-risk changes

**Characteristics**:
- ✅ Mandatory brainstorming for all complex stories (complexity >= 5)
- ✅ Two-stage review (spec + code quality) always enabled
- ✅ TDD enforcement for new features
- ✅ Human checkpoints at key decisions
- ✅ Detailed progress reporting

**When to use**:
- Starting a new project
- Implementing critical features
- High-stakes production changes
- Learning claude-loop capabilities

### Autonomous Mode

**Best for**: Routine features, well-understood patterns, trusted codebase

**Characteristics**:
- ⚪ Optional brainstorming (user triggered only)
- ⚪ Code review optional (can enable with --review)
- ⚪ TDD optional (user triggered)
- ✅ Experience retrieval from past sessions
- ✅ Adaptive story splitting for complex tasks
- ✅ Fast execution

**When to use**:
- Routine CRUD operations
- Well-established patterns
- Non-critical features
- Rapid prototyping

### Hybrid Mode (Default)

**Best for**: Most projects, balanced approach

**Characteristics**:
- ⚡ Auto brainstorming when complexity >= 5 or design keywords
- ✅ Two-stage review enabled
- ⚡ TDD enforcement for new features (auto-detected)
- ✅ Experience retrieval
- ✅ Adaptive splitting
- ⚡ Smart checkpoints based on complexity

**When to use**:
- General development work
- Mixed feature complexity
- Team collaboration
- Default recommended mode

## Configuration

### config.yaml

```yaml
execution_mode:
  # Mode: interactive, autonomous, hybrid (default)
  mode: hybrid

  # Feature toggles by mode
  interactive:
    brainstorming:
      enabled: true
      mandatory: true
    review:
      enabled: true
      two_stage: true
    tdd:
      enabled: true
      strict: true
    checkpoints:
      enabled: true
      frequency: high

  autonomous:
    brainstorming:
      enabled: false
      user_triggered_only: true
    review:
      enabled: false
      on_demand: true
    tdd:
      enabled: false
      user_triggered_only: true
    experience:
      enabled: true
      auto_retrieve: true
    splitting:
      enabled: true
      adaptive: true

  hybrid:
    brainstorming:
      enabled: true
      auto_trigger_complexity: 5
      auto_trigger_keywords: ["design", "architect", "refactor"]
    review:
      enabled: true
      two_stage: true
    tdd:
      enabled: true
      auto_detect: true
    experience:
      enabled: true
      auto_retrieve: true
    splitting:
      enabled: true
      adaptive: true
    checkpoints:
      enabled: true
      frequency: medium
```

### Command-Line Override

```bash
# Override mode for this run
./claude-loop.sh --prd prd.json --mode interactive
./claude-loop.sh --prd prd.json --mode autonomous
./claude-loop.sh --prd prd.json --mode hybrid  # default
```

### Environment Variables

```bash
# Set default mode via environment
export CLAUDE_LOOP_MODE=interactive
./claude-loop.sh --prd prd.json
```

## Mode Selection Logic

### Automatic Mode Selection

```bash
# In claude-loop.sh
select_execution_mode() {
    local complexity="$1"
    local keywords="$2"

    # Check explicit flags first
    if [ -n "$MODE_OVERRIDE" ]; then
        echo "$MODE_OVERRIDE"
        return
    fi

    # Check config
    local config_mode
    config_mode=$(yq eval '.execution_mode.mode // "hybrid"' config.yaml 2>/dev/null || echo "hybrid")

    # Apply mode
    case "$config_mode" in
        interactive)
            BRAINSTORM_MANDATORY=true
            REVIEW_ENABLED=true
            TDD_ENFORCEMENT=true
            ;;
        autonomous)
            BRAINSTORM_MANDATORY=false
            REVIEW_ENABLED=false
            TDD_ENFORCEMENT=false
            EXPERIENCE_RETRIEVAL=true
            ADAPTIVE_SPLITTING=true
            ;;
        hybrid)
            # Auto-enable based on complexity
            if [ "$complexity" -ge 5 ]; then
                BRAINSTORM_AUTO=true
            fi
            REVIEW_ENABLED=true
            TDD_AUTO_DETECT=true
            EXPERIENCE_RETRIEVAL=true
            ;;
    esac

    echo "$config_mode"
}
```

## Feature Matrix

| Feature | Interactive | Autonomous | Hybrid |
|---------|-------------|------------|--------|
| **Brainstorming** | Mandatory (all complex) | User-triggered only | Auto (complexity ≥5) |
| **Two-Stage Review** | Always enabled | Optional (--review) | Enabled by default |
| **TDD Enforcement** | Strict enforcement | User-triggered | Auto-detect new features |
| **Experience Retrieval** | Enabled | Enabled | Enabled |
| **Adaptive Splitting** | Enabled | Enabled | Enabled |
| **Human Checkpoints** | High frequency | Minimal | Medium frequency |
| **Progress Reporting** | Detailed | Concise | Balanced |

## Usage Examples

### Example 1: Interactive Mode for Critical Feature

```bash
# Start new authentication system (high risk)
./claude-loop.sh --prd auth-system-prd.json --mode interactive

# Result:
# - Mandatory brainstorming session for design
# - Two-stage review (spec + code quality)
# - TDD enforcement for all new code
# - Detailed progress updates
# - Human checkpoints at key decisions
```

### Example 2: Autonomous Mode for CRUD Operations

```bash
# Generate standard CRUD endpoints (low risk)
./claude-loop.sh --prd user-crud-prd.json --mode autonomous

# Result:
# - Fast execution
# - No mandatory workflows
# - Experience retrieval from past CRUD operations
# - Adaptive splitting if needed
# - Minimal checkpoints
```

### Example 3: Hybrid Mode (Default)

```bash
# Mixed complexity feature (recommended)
./claude-loop.sh --prd mixed-feature-prd.json --mode hybrid

# Result:
# - Auto brainstorming if complexity ≥5
# - Two-stage review enabled
# - TDD auto-detected for new features
# - Experience retrieval
# - Smart checkpoints based on complexity
```

## Best Practices

### Start Interactive, Move to Hybrid

```bash
# Phase 1: Project setup (interactive)
./claude-loop.sh --prd setup-prd.json --mode interactive

# Phase 2: Core features (hybrid)
./claude-loop.sh --prd core-features-prd.json --mode hybrid

# Phase 3: Routine work (autonomous possible)
./claude-loop.sh --prd enhancements-prd.json --mode autonomous
```

### Override for Specific Stories

```yaml
# In prd.json
{
  "userStories": [
    {
      "id": "US-001",
      "title": "Critical auth feature",
      "execution_mode": "interactive"  # Override for this story
    },
    {
      "id": "US-002",
      "title": "Simple CRUD",
      "execution_mode": "autonomous"
    }
  ]
}
```

### Team Conventions

```yaml
# config.yaml - Team standard
execution_mode:
  mode: hybrid  # Team default

  # Team-specific tweaks
  hybrid:
    brainstorming:
      auto_trigger_complexity: 6  # Slightly higher threshold
    tdd:
      enabled: true
      strict: false  # Warnings instead of blocks
```

## Metrics

**Expected Impact by Mode**:

**Interactive**:
- Setup time: +20% (worth it for critical features)
- Quality: +40% (mandatory workflows)
- Rework: -60% (caught early)

**Autonomous**:
- Execution speed: +50% (minimal workflows)
- Suitable for: ~30% of stories (routine work)
- Requires: High confidence in codebase

**Hybrid** (Recommended):
- Balance: 80/20 rule (80% of benefits, 20% of overhead)
- Suitable for: ~90% of projects
- Adapts: To story complexity automatically

## Related Features

- **US-001**: SessionStart Hooks (auto-loads mode configuration)
- **US-002**: Mandatory Skills (enforced in interactive/hybrid modes)
- **US-004**: Brainstorming (mandatory in interactive, auto in hybrid)
- **US-005**: Two-Stage Review (enabled in interactive/hybrid)
- **US-006**: TDD Enforcement (strict in interactive, auto in hybrid)

## Feedback

Have suggestions for new execution modes or mode configurations? Open an issue or submit a PR!

**Related Documentation**:
- [Session Hooks](./session-hooks.md)
- [Mandatory Skills](./mandatory-skills.md)
- [Brainstorming](./brainstorming.md)
- [Two-Stage Review](./two-stage-review.md)
- [TDD Enforcement](./tdd-enforcement.md)
