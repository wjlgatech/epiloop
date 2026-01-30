# Example Adapter

This is an example adapter demonstrating the claude-loop domain adapter extension system.

## Capabilities

- **prompts**: CLI-specific prompt templates
- **validators**: CLI argument and output validators
- **tools**: CLI-specific tool definitions
- **embeddings**: CLI-optimized embedding configuration

## Usage

This adapter is enabled by default for `cli_tool` domain projects.

## Structure

```
.example/
  adapter.json      # Adapter manifest
  README.md         # This file
  CHANGELOG.md      # Version history
  prompts/          # Prompt templates
  validators/       # Python validators
  tools/            # Tool definitions (JSON)
  embeddings/       # Embedding configuration
```

## Creating Your Own Adapter

1. Copy this directory as a template
2. Update `adapter.json` with your adapter's details
3. Add your capabilities to the appropriate directories
4. Test with `python3 lib/domain-adapter.py info your-adapter`
