# Skills Architecture - API Documentation

**Feature:** US-201 - Skills Architecture Core Framework
**Status:** Implemented
**Version:** 1.0.0

## Overview

The Skills Architecture implements Cowork-style progressive disclosure for deterministic operations in claude-loop. It uses a three-layer approach to minimize upfront token costs while providing powerful extensibility.

## Architecture Layers

### 1. Metadata Layer (Always Loaded)

The first 20 lines of each SKILL.md file are loaded at startup to populate the skills registry.

**Cost:** ~50-100 tokens per skill
**When:** Application startup
**Content:**
- Skill name
- Brief description
- Usage pattern
- Tags/categories

**Example:**
```markdown
# /example-skill - Brief Description

Short description of what this skill does in one line.

## Usage
```
/example-skill [args]
```
```

### 2. Instructions Layer (On-Demand)

Full SKILL.md documentation is loaded only when the skill is triggered.

**Cost:** ~200-500 tokens per invocation
**When:** Skill execution
**Content:**
- Complete documentation
- Parameter details
- Examples
- Implementation notes

### 3. Resources Layer (Zero Upfront Cost)

Executable scripts in the `scripts/` directory are never loaded into context.

**Cost:** 0 tokens
**When:** Never loaded into LLM context
**Content:**
- Bash scripts (`main.sh`)
- Python scripts (`main.py`)
- Node.js scripts (`main.js`)

## Skill Structure

### Directory Layout

```
skills/
├── skill-name/
│   ├── SKILL.md          # Metadata + Instructions
│   ├── scripts/          # Optional executable resources
│   │   └── main.{sh,py,js}
│   └── tests/            # Optional skill tests
│       └── test_skill.sh
```

### SKILL.md Format

```markdown
# /skill-name - One-Line Description

Brief description (metadata layer - keep under 100 tokens).

## Usage
```
/skill-name [args]
```

## What This Skill Does

Detailed description (instructions layer - loaded on-demand).

## Parameters

- `arg1` - Description of first argument
- `arg2` - Description of second argument

## Examples

```bash
./claude-loop.sh --skill skill-name
./claude-loop.sh --skill skill-name --skill-arg "value1"
```

## Implementation Details

Details about the script implementation (if applicable).
```

## Skills Framework API

### Bash API

Source the skills framework in your scripts:

```bash
source lib/skills-framework.sh

# Initialize framework
init_skills_framework "./skills"

# Load metadata for all skills
load_skills_metadata "$SKILLS_DIR"

# Get all skills metadata
get_skills_metadata

# Get specific skill metadata
get_skill_metadata "skill-name"

# Check if skill exists
if skill_exists "skill-name"; then
    echo "Skill exists"
fi

# Load full instructions
load_skill_instructions "skill-name"

# Execute skill
execute_skill "skill-name" "arg1" "arg2"

# Execute skill script directly
execute_skill_script "skill-name" "arg1" "arg2"

# List all skills
list_skills "text"  # or "json"

# Search skills by keyword
search_skills "keyword"

# Validate skill structure
validate_skill "skill-name"

# Clear cache
clear_skills_cache
```

### CLI API

```bash
# List all available skills
./claude-loop.sh --list-skills

# Execute a skill
./claude-loop.sh --skill <skill-name>

# Execute skill with arguments
./claude-loop.sh --skill <skill-name> --skill-arg "arg1" --skill-arg "arg2"
```

## Creating Skills

### Documentation-Only Skills

Skills that provide guidance without executable scripts:

```markdown
# /my-skill - Description

Guidance text that Claude will read and follow.

## What To Do

Step-by-step instructions for the LLM to follow.
```

**Example:** `/prd`, `/claude-loop`

### Executable Skills

Skills with scripts that perform deterministic operations:

1. Create skill directory:
```bash
mkdir -p skills/my-skill/scripts
```

2. Create SKILL.md:
```markdown
# /my-skill - Brief Description

Description here.

## Usage
```
/my-skill [args]
```
```

3. Create executable script:
```bash
# skills/my-skill/scripts/main.sh
#!/bin/bash
echo "Hello from my skill!"
echo "Args: $@"
exit 0
```

4. Make executable:
```bash
chmod +x skills/my-skill/scripts/main.sh
```

### Supported Script Types

The framework automatically detects and executes:

| Extension | Interpreter | Example |
|-----------|-------------|---------|
| `.sh` | `bash` | `bash main.sh args...` |
| `.py` | `python3` | `python3 main.py args...` |
| `.js` | `node` | `node main.js args...` |

### Script Interface

Scripts receive arguments as command-line parameters:

```bash
# Invocation
./claude-loop.sh --skill my-skill --skill-arg "foo" --skill-arg "bar"

# Script receives
$1 = "foo"
$2 = "bar"
```

### Exit Codes

Scripts should follow standard conventions:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Invalid arguments |
| `>2` | Skill-specific errors |

### Output Conventions

- **stdout**: Normal output, progress messages
- **stderr**: Error messages, warnings

## Token Optimization

### Metadata Extraction

Only the first 20 lines of SKILL.md are read for metadata:

```markdown
# /skill-name - Description      <- Line 1-3: Title
                                  <- Line 4: Description
Brief description text.          <- Line 5-10: More description

## Usage                          <- Line 11-20: Usage pattern
```
/skill-name [args]
```
```

**Best Practice:** Keep critical metadata in first 20 lines.

### On-Demand Loading

Full instructions are only loaded when needed:

```bash
# Startup: Only metadata loaded (~50 tokens/skill)
load_skills_metadata "$SKILLS_DIR"

# Execution: Full instructions loaded (~200 tokens)
execute_skill "skill-name"
```

### Zero-Cost Execution

Scripts are executed outside LLM context:

```bash
# This costs 0 tokens - script runs in shell
execute_skill_script "skill-name" "args"
```

## Skills Registry

### Metadata Cache

Skills metadata is cached for performance:

```
.claude-loop/skills-cache/
└── metadata.json
```

Format:
```json
[
  {
    "name": "skill-name",
    "title": "Brief Description",
    "description": "Longer description",
    "usage": "/skill-name [args]",
    "path": "/path/to/SKILL.md",
    "has_scripts": true
  }
]
```

### Cache Management

```bash
# Clear cache to force reload
clear_skills_cache

# Reload metadata
load_skills_metadata "$SKILLS_DIR"
```

## Testing Skills

### Manual Testing

```bash
# Test skill directly
./claude-loop.sh --skill my-skill

# Test with arguments
./claude-loop.sh --skill my-skill --skill-arg "test"

# Test script directly
skills/my-skill/scripts/main.sh "test"
```

### Automated Testing

Create test scripts in `skills/skill-name/tests/`:

```bash
#!/bin/bash
# tests/test_my_skill.sh

# Source skills framework
source lib/skills-framework.sh
init_skills_framework "./skills"

# Test skill exists
if ! skill_exists "my-skill"; then
    echo "FAIL: Skill not found"
    exit 1
fi

# Test skill execution
output=$(execute_skill_script "my-skill" "test" 2>&1)
if [[ "$output" != *"expected"* ]]; then
    echo "FAIL: Unexpected output"
    exit 1
fi

echo "PASS: All tests passed"
exit 0
```

### Integration Tests

See `tests/skills/` for integration test examples.

## Performance Considerations

### Token Costs

| Operation | Cost (tokens) | When |
|-----------|---------------|------|
| Load metadata | ~50 per skill | Startup |
| Load instructions | ~200-500 | On-demand |
| Execute script | 0 | Never in context |

**Example:** 10 skills = ~500 tokens at startup, 0 tokens during execution

### Caching Strategy

- Metadata cached on first load
- Cache invalidated when SKILL.md modified
- Scripts never cached (always fresh execution)

### Lazy Loading

- Full instructions loaded only when triggered
- Scripts loaded/parsed only when executed
- Unused skills cost only ~50 tokens each

## Security Considerations

### Script Execution

Scripts run with the same permissions as claude-loop:

- **Sandboxing:** Scripts are NOT sandboxed
- **Trust:** Only execute trusted skills
- **Review:** Review script content before execution

### Path Traversal

Skill names are validated to prevent path traversal:

```bash
# Blocked
./claude-loop.sh --skill "../../../etc/passwd"

# Allowed
./claude-loop.sh --skill "valid-skill-name"
```

### Command Injection

Skill arguments are properly quoted:

```bash
# Safe
execute_skill_script "skill" "arg; rm -rf /"
# Executes: main.sh "arg; rm -rf /" (as single arg)
```

## Best Practices

### 1. Minimal Metadata

Keep first 20 lines concise:
- Name and brief description
- Usage pattern
- No implementation details

### 2. Detailed Instructions

Full documentation can be extensive:
- Complete parameter descriptions
- Multiple examples
- Edge cases and error handling

### 3. Script Modularity

Keep scripts focused:
- One responsibility per script
- Clear input/output contract
- Comprehensive error handling

### 4. Documentation

Document behavior clearly:
- What the skill does
- Expected inputs and outputs
- Error conditions

### 5. Testing

Test thoroughly:
- Unit tests for scripts
- Integration tests with framework
- Error case coverage

## Troubleshooting

### Skill Not Found

```
Error: Skill 'my-skill' not found
```

**Solutions:**
1. Check skill directory exists: `ls -la skills/my-skill/`
2. Verify SKILL.md exists: `ls skills/my-skill/SKILL.md`
3. Clear cache: `rm -rf .claude-loop/skills-cache/`
4. Reload: `./claude-loop.sh --list-skills`

### Script Not Executable

```
Error: Skill 'my-skill' has no main script
```

**Solutions:**
1. Create script: `touch skills/my-skill/scripts/main.sh`
2. Make executable: `chmod +x skills/my-skill/scripts/main.sh`
3. Verify: `ls -l skills/my-skill/scripts/main.sh`

### Script Execution Failed

```
Script exited with code 1
```

**Solutions:**
1. Test script directly: `skills/my-skill/scripts/main.sh args`
2. Check stderr output for errors
3. Verify script has proper shebang: `#!/bin/bash`
4. Check file permissions

## Examples

### Example 1: Documentation Skill

```markdown
# /code-review - Code Review Guidelines

Provides guidelines for reviewing pull requests.

## Usage
```
/code-review
```

## What This Skill Does

Instructs Claude on best practices for code review...
```

Usage:
```bash
./claude-loop.sh --skill code-review
```

### Example 2: Executable Skill

```bash
# skills/git-status/scripts/main.sh
#!/bin/bash
git status --short --branch
exit $?
```

```markdown
# /git-status - Show Git Repository Status

Quick git status in short format.

## Usage
```
/git-status
```
```

Usage:
```bash
./claude-loop.sh --skill git-status
```

### Example 3: Parameterized Skill

```bash
# skills/run-tests/scripts/main.sh
#!/bin/bash
pattern="${1:-*}"
pytest -v "tests/${pattern}.py"
exit $?
```

Usage:
```bash
./claude-loop.sh --skill run-tests --skill-arg "test_api"
```

## Comparison with Other Patterns

### Skills vs Agents

| Feature | Skills | Agents |
|---------|--------|--------|
| Purpose | Deterministic ops | Autonomous reasoning |
| Token Cost | 0 (scripts) | High (full context) |
| Control | Explicit invocation | Auto-selected |
| Speed | Instant | LLM latency |
| Use Case | Tools, utilities | Complex tasks |

### Skills vs Direct Script Execution

| Feature | Skills | Direct Scripts |
|---------|--------|----------------|
| Discovery | Automatic | Manual path |
| Documentation | Integrated | Separate |
| Token Cost | Optimized | N/A |
| Context | LLM-aware | Standalone |

## Future Enhancements

Planned improvements (not yet implemented):

1. **Skill Dependencies:** Skills can depend on other skills
2. **Skill Composition:** Chain skills together
3. **Skill Validation:** Validate inputs/outputs
4. **Skill Versioning:** Version control for skills
5. **Skill Marketplace:** Share skills across projects

## References

- **US-201:** Skills Architecture Core Framework
- **US-202:** Priority Skills Implementation
- **Progressive Disclosure:** Cowork UX pattern
- **Token Optimization:** Context window management

## Changelog

### v1.0.0 (2026-01-13)

- Initial implementation (US-201)
- Three-layer architecture
- Bash/Python/Node.js support
- CLI integration
- Documentation and examples
