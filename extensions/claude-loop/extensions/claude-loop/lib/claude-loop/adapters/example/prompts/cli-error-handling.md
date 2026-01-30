# CLI Error Handling Prompt

When handling CLI errors, follow these guidelines:

## Exit Codes
- 0: Success
- 1: General error
- 2: Invalid arguments
- 126: Permission denied
- 127: Command not found
- 128+N: Killed by signal N

## Common Error Patterns

### Argument Parsing
- Check for required arguments first
- Validate argument types before processing
- Provide helpful error messages with usage examples

### File Operations
- Check file existence before reading
- Handle permission errors gracefully
- Create parent directories when writing

### External Commands
- Check if command exists before execution
- Capture both stdout and stderr
- Set appropriate timeouts
