# /hello-world - Example Skill with Script Execution

A simple example skill demonstrating the skills architecture with executable scripts.

## Usage

```
/hello-world
/hello-world --skill-arg "Your Name"
./claude-loop.sh --skill hello-world
./claude-loop.sh --skill hello-world --skill-arg "Alice"
```

## What This Skill Does

Demonstrates the three-layer skills architecture:
1. **Metadata Layer**: This header and description (always loaded, <100 tokens)
2. **Instructions Layer**: Full documentation below (loaded on-demand)
3. **Resources Layer**: Executable script in scripts/ directory (executed when needed)

## Behavior

When executed without arguments:
- Displays a simple "Hello, World!" message
- Shows execution timestamp
- Demonstrates metadata loading and script execution

When executed with an argument:
- Displays "Hello, [Name]!" where [Name] is the provided argument
- Shows personalized greeting
- Demonstrates parameter passing to scripts

## Architecture Example

This skill demonstrates the progressive disclosure pattern:

```
skills/hello-world/
├── SKILL.md           # Metadata + Instructions (this file)
└── scripts/
    └── main.sh        # Executable script (zero upfront cost)
```

### Metadata Layer (Always Loaded)
The first 20 lines of SKILL.md are loaded at startup to populate the skills list.
This includes: name, description, and usage pattern.

Cost: ~50 tokens per skill

### Instructions Layer (On-Demand)
The full SKILL.md content is only loaded when the skill is triggered.
Provides context and documentation for skill execution.

Cost: ~200 tokens when triggered

### Resources Layer (Zero Upfront Cost)
The scripts/ directory contains executable code that is never loaded into context.
Scripts are executed directly by the shell/interpreter.

Cost: 0 tokens (executed outside LLM context)

## Script Interface

The main.sh script receives arguments as command-line parameters:

```bash
# No arguments
./skills/hello-world/scripts/main.sh

# With arguments
./skills/hello-world/scripts/main.sh "Alice" "Bob"
```

## Example Output

**No arguments:**
```
Hello, World!
Executed at: 2026-01-13 14:30:00
```

**With argument "Alice":**
```
Hello, Alice!
Executed at: 2026-01-13 14:30:00
```

## Implementation Details

### Script Language Support

The skills framework supports multiple script languages:
- `main.sh` - Bash scripts
- `main.py` - Python scripts
- `main.js` - Node.js scripts

### Exit Codes

Scripts should follow standard exit code conventions:
- `0` - Success
- `1` - General error
- `2` - Invalid arguments

### Output Conventions

Scripts should output to stdout for normal messages and stderr for errors.

## Integration with claude-loop

Skills can be invoked during claude-loop execution:

```bash
# List all skills
./claude-loop.sh --list-skills

# Execute skill
./claude-loop.sh --skill hello-world

# Execute with arguments
./claude-loop.sh --skill hello-world --skill-arg "Alice" --skill-arg "Bob"
```

## Tips for Skill Development

1. **Keep metadata concise**: First 20 lines should be < 100 tokens
2. **Detailed instructions**: Full documentation can be longer (on-demand loaded)
3. **Executable scripts**: Place heavy logic in scripts/ directory
4. **Clear interface**: Document parameters and exit codes
5. **Error handling**: Scripts should handle errors gracefully

## Related Skills

- `/prd` - Generate PRD from feature description
- `/claude-loop` - Convert PRD.md to prd.json

## Further Reading

See docs/features/skills-architecture.md for complete skills API documentation.
