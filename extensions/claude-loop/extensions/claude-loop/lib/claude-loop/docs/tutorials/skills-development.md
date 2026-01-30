# Skills Development Tutorial

Learn how to create custom skills for claude-loop using the three-layer progressive disclosure architecture.

## Table of Contents

- [What are Skills?](#what-are-skills)
- [Skills Architecture](#skills-architecture)
- [Creating Your First Skill](#creating-your-first-skill)
- [Advanced Skill Development](#advanced-skill-development)
- [Testing Skills](#testing-skills)
- [Best Practices](#best-practices)
- [Examples](#examples)

## What are Skills?

Skills are deterministic operations that execute instantly without AI. They provide:

- **Zero AI cost** - No token usage
- **Instant execution** - Typically under 1 second
- **Consistent results** - Same input, same output
- **Progressive disclosure** - Load metadata first, instructions on-demand

### When to Create a Skill

Create a skill when you have:

- **Deterministic logic** - The operation has predictable outputs
- **Reusable operations** - The task is performed frequently
- **Fast execution** - The operation completes in seconds
- **Clear inputs/outputs** - Well-defined parameters and results

### When NOT to Create a Skill

Don't create a skill for:

- **Non-deterministic tasks** - Requires AI reasoning or creativity
- **Long-running operations** - Takes minutes or hours
- **One-time operations** - Not reusable
- **Complex decision-making** - Requires context and judgment

## Skills Architecture

Claude-loop uses a three-layer progressive disclosure architecture:

### Layer 1: Metadata (Always Loaded)

- **Size**: First 20 lines of SKILL.md (~50 tokens/skill)
- **Purpose**: Skill discovery and listing
- **Contents**: Name, version, description, usage, author

```markdown
# Skill: my-skill
# Version: 1.0.0
# Description: A short one-line description of what this skill does
# Usage: --skill my-skill --skill-arg <argument>
# Author: Your Name
```

### Layer 2: Instructions (On-Demand)

- **Size**: Full SKILL.md content (200-500 tokens)
- **Purpose**: Execution guidance
- **Contents**: Detailed description, parameters, examples, error handling

### Layer 3: Resources (Zero Upfront Cost)

- **Size**: Variable (depends on script complexity)
- **Purpose**: Actual execution
- **Contents**: Bash/Python/Node.js scripts

## Creating Your First Skill

Let's create a simple skill that counts lines in a file.

### Step 1: Create Skill Directory

```bash
mkdir -p skills/line-counter/{scripts,tests}
```

### Step 2: Create SKILL.md

Create `skills/line-counter/SKILL.md`:

```markdown
# Skill: line-counter
# Version: 1.0.0
# Description: Count lines in a file or directory
# Usage: --skill line-counter --skill-arg <file-or-directory>
# Author: Your Name
# Tags: file-analysis, statistics
# Category: utility
# Complexity: simple
# Estimated-Time: <1s
# Dependencies: none
# Compatibility: macOS, Linux
#
# Parameters:
# - <file-or-directory>: Path to file or directory to analyze
#
# Output:
# - Line count for each file
# - Total line count
# - File count
#
# Exit Codes:
# - 0: Success
# - 1: Path not found
# - 2: Permission denied

---

## Description

This skill counts the total number of lines in a file or all files in a directory.
It recursively traverses directories and counts lines in all text files.

## Examples

Count lines in a single file:
```bash
./claude-loop.sh --skill line-counter --skill-arg myfile.txt
```

Count lines in a directory:
```bash
./claude-loop.sh --skill line-counter --skill-arg src/
```

## Error Handling

- If path doesn't exist, exits with code 1
- If permission denied, exits with code 2
- Binary files are automatically skipped
- Empty files count as 0 lines

## Implementation Notes

Uses `wc -l` for fast line counting. Falls back to manual counting if `wc` unavailable.
```

### Step 3: Create Execution Script

Create `skills/line-counter/scripts/main.sh`:

```bash
#!/usr/bin/env bash
# Line Counter Skill - Execution Script

set -euo pipefail

# Get argument
if [ $# -eq 0 ]; then
    echo "Error: No path provided" >&2
    echo "Usage: $0 <file-or-directory>" >&2
    exit 1
fi

PATH_TO_COUNT="$1"

# Check if path exists
if [ ! -e "$PATH_TO_COUNT" ]; then
    echo "Error: Path not found: $PATH_TO_COUNT" >&2
    exit 1
fi

# Function to count lines in a file
count_lines_in_file() {
    local file="$1"

    # Skip binary files
    if file "$file" | grep -q "text"; then
        wc -l < "$file" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Main logic
if [ -f "$PATH_TO_COUNT" ]; then
    # Single file
    lines=$(count_lines_in_file "$PATH_TO_COUNT")
    echo "File: $PATH_TO_COUNT"
    echo "Lines: $lines"
    echo "Total: $lines lines in 1 file"
else
    # Directory
    total_lines=0
    file_count=0

    echo "Analyzing directory: $PATH_TO_COUNT"
    echo ""

    while IFS= read -r -d '' file; do
        lines=$(count_lines_in_file "$file")
        if [ "$lines" -gt 0 ]; then
            echo "  $file: $lines lines"
            total_lines=$((total_lines + lines))
            file_count=$((file_count + 1))
        fi
    done < <(find "$PATH_TO_COUNT" -type f -print0)

    echo ""
    echo "Total: $total_lines lines in $file_count files"
fi

exit 0
```

Make it executable:

```bash
chmod +x skills/line-counter/scripts/main.sh
```

### Step 4: Test Your Skill

```bash
# Test with a single file
./claude-loop.sh --skill line-counter --skill-arg README.md

# Test with a directory
./claude-loop.sh --skill line-counter --skill-arg lib/

# Verify it appears in the list
./claude-loop.sh --list-skills | grep line-counter
```

## Advanced Skill Development

### Using Python

For more complex logic, use Python:

Create `skills/my-skill/scripts/main.py`:

```python
#!/usr/bin/env python3
"""
My Skill - Python Implementation
"""

import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Error: No argument provided", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]

    # Your logic here
    result = process_argument(arg)

    # Output as JSON
    print(json.dumps(result, indent=2))

    return 0

def process_argument(arg: str) -> dict:
    """Process the argument and return results."""
    # Your processing logic
    return {
        "status": "success",
        "argument": arg,
        "result": "processed"
    }

if __name__ == "__main__":
    sys.exit(main())
```

Make it executable:

```bash
chmod +x skills/my-skill/scripts/main.py
```

### Accepting Multiple Arguments

Skills can accept multiple arguments:

```bash
./claude-loop.sh --skill my-skill \
    --skill-arg "arg1" \
    --skill-arg "arg2" \
    --skill-arg "arg3"
```

In your script:

```bash
#!/usr/bin/env bash
set -euo pipefail

# All arguments available in $@
for arg in "$@"; do
    echo "Processing: $arg"
done
```

### Output Formats

Skills can output in various formats:

**Plain text** (default):
```bash
echo "Result: success"
echo "Count: 42"
```

**JSON** (recommended for structured data):
```bash
cat <<EOF
{
  "status": "success",
  "count": 42,
  "files": ["file1.txt", "file2.txt"]
}
EOF
```

**Table format**:
```bash
printf "%-20s %10s\n" "File" "Lines"
printf "%-20s %10s\n" "----" "-----"
printf "%-20s %10d\n" "file1.txt" 100
printf "%-20s %10d\n" "file2.txt" 200
```

### Error Handling

Use meaningful exit codes:

```bash
# Success
exit 0

# General error
exit 1

# Specific errors
exit 2  # Invalid argument
exit 3  # Permission denied
exit 4  # File not found
exit 5  # Network error
```

Log errors to stderr:

```bash
echo "Error: Something went wrong" >&2
exit 1
```

### Configuration Files

Skills can read configuration from `.claude-loop/skills-config/`:

```bash
CONFIG_DIR=".claude-loop/skills-config"
CONFIG_FILE="$CONFIG_DIR/my-skill.json"

if [ -f "$CONFIG_FILE" ]; then
    # Read configuration
    timeout=$(jq -r '.timeout' "$CONFIG_FILE")
fi
```

## Testing Skills

### Manual Testing

```bash
# Test directly
./skills/my-skill/scripts/main.sh test-argument

# Test via claude-loop
./claude-loop.sh --skill my-skill --skill-arg test-argument
```

### Automated Testing

Create `skills/my-skill/tests/test_my_skill.sh`:

```bash
#!/usr/bin/env bash

set -euo pipefail

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

# Test function
test_case() {
    local description="$1"
    local expected="$2"
    local command="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    echo -n "Test $TESTS_RUN: $description ... "

    if output=$(eval "$command" 2>&1); then
        if echo "$output" | grep -q "$expected"; then
            echo "PASS"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo "FAIL"
            echo "  Expected: $expected"
            echo "  Got: $output"
        fi
    else
        echo "FAIL (exit code $?)"
    fi
}

# Run tests
test_case "Basic execution" "success" \
    "../scripts/main.sh test-arg"

test_case "Multiple arguments" "arg2" \
    "../scripts/main.sh arg1 arg2 arg3"

test_case "Error handling" "Error:" \
    "../scripts/main.sh"

# Summary
echo ""
echo "Tests: $TESTS_PASSED/$TESTS_RUN passed"

if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
    exit 0
else
    exit 1
fi
```

Run tests:

```bash
cd skills/my-skill/tests
./test_my_skill.sh
```

## Best Practices

### 1. Keep Metadata Concise

The first 20 lines are always loaded, so keep them minimal:

```markdown
# Skill: name
# Version: 1.0.0
# Description: One-line description (< 80 chars)
# Usage: --skill name --skill-arg <arg>
# Author: Your Name
```

### 2. Use Descriptive Names

Good names:
- `prd-validator`
- `test-scaffolder`
- `commit-formatter`

Bad names:
- `tool1`
- `helper`
- `script`

### 3. Document Exit Codes

```markdown
# Exit Codes:
# - 0: Success
# - 1: Invalid argument
# - 2: File not found
# - 3: Permission denied
```

### 4. Provide Examples

Include at least 2-3 examples in SKILL.md:

```markdown
## Examples

Basic usage:
```bash
./claude-loop.sh --skill my-skill --skill-arg input.txt
```

With multiple files:
```bash
./claude-loop.sh --skill my-skill --skill-arg "file1.txt" --skill-arg "file2.txt"
```
```

### 5. Use Portable Code

Ensure compatibility across platforms:

```bash
# Good: Portable
if [ -f "$file" ]; then
    echo "File exists"
fi

# Bad: Not portable
[[ -f "$file" ]] && echo "File exists"
```

### 6. Handle Edge Cases

```bash
# Empty input
if [ -z "$arg" ]; then
    echo "Error: Empty argument" >&2
    exit 1
fi

# Invalid path
if [ ! -e "$path" ]; then
    echo "Error: Path not found" >&2
    exit 1
fi

# Permission check
if [ ! -r "$file" ]; then
    echo "Error: Permission denied" >&2
    exit 3
fi
```

### 7. Version Your Skills

Update version in SKILL.md when making changes:

```markdown
# Skill: my-skill
# Version: 1.1.0  # Incremented from 1.0.0
```

## Examples

### Example 1: File Converter

```markdown
# Skill: file-converter
# Version: 1.0.0
# Description: Convert files between formats (JSON, YAML, TOML)
# Usage: --skill file-converter --skill-arg <input-file> --skill-arg <output-format>
# Author: Claude Loop Team
```

Script:
```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="$1"
OUTPUT_FORMAT="$2"

case "$OUTPUT_FORMAT" in
    json)
        python3 -c "import yaml, json; print(json.dumps(yaml.safe_load(open('$INPUT_FILE'))))"
        ;;
    yaml)
        python3 -c "import yaml, json; print(yaml.dump(json.load(open('$INPUT_FILE'))))"
        ;;
    *)
        echo "Error: Unsupported format: $OUTPUT_FORMAT" >&2
        exit 1
        ;;
esac
```

### Example 2: Code Statistics

```markdown
# Skill: code-stats
# Version: 1.0.0
# Description: Generate code statistics (LOC, files, complexity)
# Usage: --skill code-stats --skill-arg <directory>
# Author: Claude Loop Team
```

Script:
```python
#!/usr/bin/env python3
import sys
from pathlib import Path
import json

def analyze_directory(directory):
    stats = {
        "total_files": 0,
        "total_lines": 0,
        "by_language": {}
    }

    for file_path in Path(directory).rglob("*"):
        if file_path.is_file():
            stats["total_files"] += 1

            ext = file_path.suffix
            if ext not in stats["by_language"]:
                stats["by_language"][ext] = {"files": 0, "lines": 0}

            stats["by_language"][ext]["files"] += 1

            try:
                with open(file_path) as f:
                    lines = len(f.readlines())
                    stats["total_lines"] += lines
                    stats["by_language"][ext]["lines"] += lines
            except:
                pass

    return stats

if __name__ == "__main__":
    directory = sys.argv[1]
    stats = analyze_directory(directory)
    print(json.dumps(stats, indent=2))
```

### Example 3: Dependency Checker

```markdown
# Skill: dependency-checker
# Version: 1.0.0
# Description: Check for outdated dependencies in package.json/requirements.txt
# Usage: --skill dependency-checker --skill-arg <package-file>
# Author: Claude Loop Team
```

## Next Steps

- **Browse existing skills**: `./claude-loop.sh --list-skills`
- **Study skill code**: Examine `skills/prd-validator/` and other bundled skills
- **Share your skills**: Submit PRs to add useful skills to the repository
- **Create skill templates**: Use existing skills as templates for new ones

## Resources

- [Skills Architecture Documentation](../features/skills-architecture.md)
- [Skills API Reference](../reference/skills-api.md)
- [Bundled Skills Source Code](../../skills/)
- [Community Skills Repository](https://github.com/yourusername/claude-loop-skills)

Happy skill development! 🛠️
