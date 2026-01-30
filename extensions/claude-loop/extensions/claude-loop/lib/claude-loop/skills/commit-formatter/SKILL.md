# /commit-formatter - Enforce Commit Message Standards

Formats and validates commit messages according to Conventional Commits specification.

## Usage

```
/commit-formatter --skill-arg MESSAGE
./claude-loop.sh --skill commit-formatter --skill-arg MESSAGE
```

## What This Skill Does

Validates and formats commit messages according to [Conventional Commits](https://www.conventionalcommits.org/):
1. **Type validation**: Ensures valid commit type (feat, fix, docs, etc.)
2. **Scope checking**: Validates optional scope format
3. **Breaking changes**: Detects and formats breaking change indicators
4. **Length validation**: Enforces subject line length limits
5. **Body formatting**: Wraps body text to 72 characters
6. **Footer validation**: Validates footer format (e.g., BREAKING CHANGE:, Refs #123)

## Conventional Commits Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Valid Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, semicolons, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes to build system or dependencies
- `ci`: Changes to CI configuration files and scripts
- `chore`: Other changes that don't modify src or test files
- `revert`: Reverts a previous commit

### Breaking Changes
- Append `!` after type/scope: `feat(api)!: remove deprecated endpoint`
- Or include `BREAKING CHANGE:` footer

## Examples

### Valid Commits

```
feat: add user authentication
feat(auth): implement JWT tokens
fix: resolve memory leak in parser
docs: update API documentation
refactor(core)!: change config format
```

### Invalid Commits (Will be Corrected)

```
Added new feature           → feat: add new feature
Fix bug                     → fix: resolve issue
Update docs                 → docs: update documentation
```

## Behavior

When executed with a commit message:
- Validates the format
- Corrects common issues automatically
- Outputs the formatted message
- Returns exit code indicating validity

## CLI Options (via --skill-arg)

```
--skill-arg "<message>"              # Commit message to format/validate
--skill-arg "<message>" --strict     # Strict mode (no auto-corrections)
--skill-arg "<message>" --interactive  # Interactive correction prompts
```

## Exit Codes

- `0` - Commit message is valid (or was corrected)
- `1` - Commit message is invalid and cannot be auto-corrected
- `2` - Invalid arguments

## Output Format

```
Commit Formatter v1.0
=====================

Original:
  Added user login feature

Formatted:
  feat: add user login feature

Status: ✓ VALID (auto-corrected)

Recommendations:
  - Consider adding a scope: feat(auth): add user login feature
  - Add body to explain why this change was made
```

## Integration with claude-loop

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/commit-msg

commit_msg_file=$1
commit_msg=$(cat "$commit_msg_file")

formatted=$(./claude-loop.sh --skill commit-formatter --skill-arg "$commit_msg")

if [ $? -eq 0 ]; then
    echo "$formatted" > "$commit_msg_file"
else
    echo "Error: Invalid commit message format"
    exit 1
fi
```

### Validate Commit History

```bash
# Check last 10 commits
git log -10 --pretty=format:"%s" | while read msg; do
    ./claude-loop.sh --skill commit-formatter --skill-arg "$msg"
done
```

## Advanced Features

### Scope Detection
Automatically suggests scopes based on file changes:
- Files in `lib/` → scope: lib
- Files in `api/` → scope: api
- Files in `docs/` → scope: docs

### Co-authored-by Support
Preserves and validates co-author trailers:
```
feat: add new feature

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Issue Reference Validation
Validates issue references in footers:
```
fix: resolve login bug

Closes #123
Refs #456, #789
```

### Emoji Support (Optional)
Can enable gitmoji-style prefixes:
```
feat: ✨ add user authentication
fix: 🐛 resolve memory leak
```

## Script Implementation

Implemented in Python for robust text processing:

- `scripts/main.py` - Main formatting logic
- Regex-based parsing
- Auto-correction heuristics
- Interactive prompts (optional)

## Tips for Good Commit Messages

1. **Use imperative mood**: "add feature" not "added feature"
2. **Be specific**: "fix login timeout" not "fix bug"
3. **Add context in body**: Explain why, not just what
4. **Reference issues**: Include issue numbers when relevant
5. **One logical change**: Each commit should be atomic

## Related Skills

- `/prd-validator` - Validate PRD structure
- `/test-scaffolder` - Generate test scaffolding

## Further Reading

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- See docs/git/commit-standards.md for project-specific guidelines
