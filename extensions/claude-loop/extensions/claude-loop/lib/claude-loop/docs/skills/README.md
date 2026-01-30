# Skills Documentation

This directory contains detailed documentation for all available claude-loop skills.

## Available Skills

### Core Skills

1. **[prd-validator](./prd-validator.md)** - Validate PRD structure and dependencies
   - Validates JSON schema compliance
   - Detects circular dependencies
   - Checks file scopes for conflicts

2. **[test-scaffolder](./test-scaffolder.md)** - Generate test file structures from code
   - Creates test boilerplate for Bash, Python, JavaScript/TypeScript
   - Extracts functions and generates test stubs
   - Mirrors directory structure in tests/

3. **[commit-formatter](./commit-formatter.md)** - Enforce commit message standards
   - Validates Conventional Commits format
   - Auto-corrects common formatting issues
   - Provides recommendations for better commit messages

4. **[api-spec-generator](./api-spec-generator.md)** - Generate OpenAPI specs from code
   - Extracts API endpoints from Flask, FastAPI, Express
   - Generates OpenAPI 3.0 specifications
   - Documents routes, methods, and parameters

5. **[cost-optimizer](./cost-optimizer.md)** - Analyze story complexity and recommend models
   - Calculates complexity scores for stories
   - Recommends optimal Claude model (Haiku/Sonnet/Opus)
   - Estimates costs and savings

### Utility Skills

- **hello-world** - Example skill demonstrating the skills architecture
- **prd** - Generate PRD from feature descriptions
- **claude-loop** - Convert PRD.md to prd.json

## Quick Start

### List All Skills

```bash
./claude-loop.sh --list-skills
```

### Execute a Skill

```bash
# With default arguments
./claude-loop.sh --skill prd-validator

# With custom arguments
./claude-loop.sh --skill prd-validator --skill-arg custom-prd.json

# Multiple arguments
./claude-loop.sh --skill test-scaffolder --skill-arg src/lib/parser.py
```

## Skills Architecture

Skills follow a three-layer progressive disclosure pattern:

1. **Metadata Layer** (Always Loaded)
   - Name, title, description
   - Usage examples
   - ~50-100 tokens per skill

2. **Instructions Layer** (On-Demand)
   - Full SKILL.md documentation
   - Loaded only when skill is triggered
   - ~200-500 tokens

3. **Resources Layer** (Zero Upfront Cost)
   - Executable scripts in scripts/ directory
   - Never loaded into LLM context
   - Executed directly by shell/interpreter

## Creating Custom Skills

See [../features/skills-architecture.md](../features/skills-architecture.md) for complete guide on creating custom skills.

### Basic Structure

```
skills/my-skill/
├── SKILL.md           # Metadata + Instructions
└── scripts/
    └── main.sh        # or main.py, main.js
```

### SKILL.md Template

```markdown
# /my-skill - Short Description

One-sentence description of what this skill does.

## Usage

\`\`\`
/my-skill
/my-skill --skill-arg <argument>
\`\`\`

## What This Skill Does

Detailed description...

## Behavior

What happens when executed...

## Exit Codes

- `0` - Success
- `1` - Error
- `2` - Invalid arguments
```

## Integration with claude-loop

Skills can be used in multiple ways:

### Pre-execution Validation

```bash
# Validate PRD before running
./claude-loop.sh --skill prd-validator --skill-arg my-prd.json && \
./claude-loop.sh
```

### Post-implementation Tasks

```bash
# Generate tests after implementing a story
./claude-loop.sh --skill test-scaffolder --skill-arg lib/new-feature.sh
```

### Commit Hooks

```bash
# In .git/hooks/commit-msg
./claude-loop.sh --skill commit-formatter --skill-arg "$1"
```

## Testing Skills

Each skill should have tests in `tests/skills/<skill-name>/`:

```bash
# Run all skill tests
./tests/skills/test_all_skills.sh

# Run specific skill tests
./tests/skills/prd-validator/test_prd_validator.sh
```

## Further Reading

- [Skills Architecture](../features/skills-architecture.md) - Complete technical documentation
- [SKILL.md Format Specification](../features/skills-architecture.md#skill-md-format)
- [Script Execution](../features/skills-architecture.md#script-execution)
