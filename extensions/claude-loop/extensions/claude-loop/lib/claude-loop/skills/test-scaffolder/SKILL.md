# /test-scaffolder - Generate Test File Structures from Code

Automatically generates test file scaffolding with boilerplate code based on source files.

## Usage

```
/test-scaffolder --skill-arg src/lib/myfile.sh
/test-scaffolder --skill-arg src/utils.py
./claude-loop.sh --skill test-scaffolder --skill-arg lib/prd-parser.sh
```

## What This Skill Does

Analyzes source code files and generates corresponding test files with:
1. **Test directory structure**: Mirrors source directory in tests/
2. **Test file boilerplate**: Language-appropriate test framework setup
3. **Test case stubs**: Extracted from functions/methods in source code
4. **Import statements**: Properly imports the code under test
5. **Assertion examples**: Placeholder assertions for each test case

## Behavior

When executed with a source file path:
- Detects the programming language from file extension
- Creates test directory structure if it doesn't exist
- Generates test file with appropriate framework (bash-test, pytest, jest, etc.)
- Extracts functions/methods from source and creates test stubs
- Outputs the path to the generated test file

## Supported Languages

### Shell/Bash (.sh)
- Test framework: bash-test or bats
- Test file: tests/filename_test.sh
- Detects functions using `function name()` or `name()` patterns

### Python (.py)
- Test framework: pytest
- Test file: tests/test_filename.py
- Detects functions and class methods
- Includes pytest fixtures template

### JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
- Test framework: jest
- Test file: filename.test.js or filename.test.ts
- Detects functions, classes, and exported members
- Includes jest describe/test blocks

### Other Languages
- Go (.go): go test framework
- Ruby (.rb): rspec framework
- Java (.java): JUnit framework

## Example Output

For a source file `lib/prd-parser.sh`:

```bash
#!/bin/bash
# Tests for lib/prd-parser.sh

source lib/prd-parser.sh

test_validate_prd() {
    # Test validate_prd function
    local result=$(validate_prd "test-prd.json")
    assertEquals "Expected validation to pass" "0" "$?"
}

test_get_ready_stories() {
    # Test get_ready_stories function
    local stories=$(get_ready_stories)
    assertNotNull "Expected stories to be returned" "$stories"
}

# Run tests
. shunit2
```

For a Python file `lib/cost_estimator.py`:

```python
import pytest
from lib.cost_estimator import estimate_cost, calculate_tokens

def test_estimate_cost():
    """Test estimate_cost function."""
    result = estimate_cost(story_id="US-001", model="sonnet")
    assert result > 0
    assert isinstance(result, float)

def test_calculate_tokens():
    """Test calculate_tokens function."""
    tokens = calculate_tokens(text="Hello, world!")
    assert tokens > 0
```

## Test Scaffolding Features

### Function/Method Detection
- Parses source file to extract function names
- Detects parameters and return types (if available)
- Handles both public and private functions

### Boilerplate Generation
- Includes necessary imports and setup code
- Adds framework-specific annotations (@Test, pytest fixtures, etc.)
- Includes teardown/cleanup templates if needed

### Smart Naming
- Test files follow language conventions
- Test function names match source function names with `test_` prefix
- Descriptive docstrings for each test case

### Directory Structure
- Mirrors source directory structure in tests/
- Creates subdirectories as needed
- Maintains consistent organization

## CLI Options (via --skill-arg)

```
--skill-arg <source_file>              # Source file to scaffold tests for
--skill-arg <source_file> --overwrite  # Overwrite existing test file
--skill-arg <source_file> --framework pytest  # Force specific framework
```

## Exit Codes

- `0` - Test file generated successfully
- `1` - Error generating test file
- `2` - Invalid arguments or source file not found

## Integration with claude-loop

Generate tests for all changed files in a story:

```bash
# After implementing a story, generate tests
git diff --name-only | while read file; do
    ./claude-loop.sh --skill test-scaffolder --skill-arg "$file"
done
```

## Advanced Features

### Context-Aware Test Generation
- Detects if function does I/O operations → adds mock fixtures
- Detects if function throws exceptions → adds exception test cases
- Detects if function takes complex objects → adds fixture factories

### Test Coverage Gaps
- Compares existing test file with source file
- Reports functions that don't have tests
- Suggests additional test cases based on code complexity

### Test Data Generation
- Creates sample test data files (fixtures)
- Generates mock objects for dependencies
- Includes edge case examples (null, empty, boundary values)

## Script Implementation

Implemented in Python for robust parsing:

- `scripts/main.py` - Main scaffolding logic
- Uses AST parsing for Python
- Uses regex for Bash/Shell
- Uses Babel parser for JavaScript/TypeScript

## Example Workflow

```bash
# 1. Implement a new feature
vim lib/new-feature.sh

# 2. Generate test scaffolding
./claude-loop.sh --skill test-scaffolder --skill-arg lib/new-feature.sh

# 3. Edit generated tests to add assertions
vim tests/lib/new-feature_test.sh

# 4. Run tests
./tests/lib/new-feature_test.sh
```

## Tips for Test Development

1. **Review generated tests**: Always review and customize generated stubs
2. **Add assertions**: Replace placeholders with meaningful assertions
3. **Add edge cases**: Supplement generated tests with boundary cases
4. **Update regularly**: Re-run scaffolder when functions change
5. **Use fixtures**: Leverage fixture templates for complex setup

## Related Skills

- `/prd-validator` - Validate PRD structure before testing
- `/commit-formatter` - Format commit messages for test additions

## Further Reading

See docs/testing/test-scaffolding.md for complete test scaffolding guide.
