# /prd-validator - Validate PRD Structure and Dependencies

Validates PRD JSON files for correctness, completeness, and circular dependencies.

## Usage

```
/prd-validator
/prd-validator --skill-arg prd.json
./claude-loop.sh --skill prd-validator
./claude-loop.sh --skill prd-validator --skill-arg custom-prd.json
```

## What This Skill Does

Validates Product Requirement Document (PRD) JSON files to ensure:
1. **Schema compliance**: All required fields are present
2. **Dependency validation**: No circular dependencies between stories
3. **File scope checking**: Referenced files exist or are in expected locations
4. **Priority ordering**: Stories have valid priority values
5. **Complexity assessment**: EstimatedComplexity values are valid

## Behavior

When executed without arguments:
- Validates the default `prd.json` file in the current directory
- Outputs validation results with pass/fail status
- Lists any errors or warnings found

When executed with a file path argument:
- Validates the specified PRD JSON file
- Reports detailed validation results
- Exits with code 0 if valid, 1 if invalid

## Validation Checks

### Required Fields
- `project` - Project name
- `branchName` - Git branch name
- `description` - Project description
- `userStories` - Array of user stories

### User Story Required Fields
- `id` - Unique story identifier (e.g., "US-001")
- `title` - Story title
- `description` - Detailed description
- `acceptanceCriteria` - Array of acceptance criteria
- `priority` - Integer priority value
- `passes` - Boolean completion status

### Optional Fields (Validated if Present)
- `dependencies` - Array of story IDs (checked for circular deps)
- `fileScope` - Array of file paths
- `estimatedComplexity` - Must be: simple, medium, or complex
- `suggestedModel` - Must be: haiku, sonnet, or opus

### Dependency Validation
- Checks for circular dependencies using graph traversal
- Verifies referenced story IDs exist in the PRD
- Ensures dependency ordering is logically possible

### File Scope Validation
- Warns about non-existent files in fileScope (soft warning)
- Checks for conflicting file scopes between parallel stories
- Validates file path formats

## Exit Codes

- `0` - PRD is valid
- `1` - PRD has errors
- `2` - Invalid arguments or file not found

## Output Format

The validator outputs a structured report:

```
PRD Validator v1.0
==================

File: prd.json
Project: my-project
Branch: feature/my-feature

✓ Schema validation: PASSED
✓ Dependency validation: PASSED
✓ File scope validation: PASSED
⚠ Warnings: 2

Warnings:
- Story US-003: File 'src/nonexistent.ts' in fileScope does not exist
- Story US-005: Priority value 10 is unusual (typically 1-5)

Summary: PRD is VALID with warnings
```

## Integration with claude-loop

This skill can be used before executing a PRD:

```bash
# Validate before running
./claude-loop.sh --skill prd-validator --skill-arg my-prd.json

# If valid, proceed with execution
./claude-loop.sh
```

## Advanced Features

### Circular Dependency Detection

Uses depth-first search to detect cycles in the dependency graph:

```
Story US-001 depends on US-002
Story US-002 depends on US-003
Story US-003 depends on US-001  ❌ CIRCULAR DEPENDENCY
```

### Parallel Safety Check

Validates that stories intended for parallel execution don't have:
- Overlapping file scopes
- Circular dependencies
- Invalid dependency chains

### JSON Schema Validation

Validates against the PRD JSON schema v2:
- Top-level parallelization config
- Story-level metadata fields
- Proper data types for all fields

## Script Implementation

The validator is implemented in Python for robust JSON parsing and graph algorithms:

- `scripts/main.py` - Main validation logic
- Uses `json` module for parsing
- Implements DFS for cycle detection
- Returns structured validation results

## Error Messages

Clear, actionable error messages:

```
ERROR: Circular dependency detected:
  US-001 -> US-002 -> US-003 -> US-001

ERROR: Invalid estimatedComplexity value: 'hard'
  Valid values: simple, medium, complex
  Story: US-005

ERROR: Missing required field 'acceptanceCriteria'
  Story: US-007
```

## Tips for PRD Authors

1. **Use sequential IDs**: US-001, US-002, etc.
2. **Validate early**: Run validator before committing PRD
3. **Fix errors**: Address all errors before execution
4. **Review warnings**: Consider warnings even if PRD is valid
5. **Test dependencies**: Ensure dependency order makes logical sense

## Related Skills

- `/cost-optimizer` - Analyze story complexity and recommend models
- `/commit-formatter` - Format commit messages for story completion

## Further Reading

See docs/prd-schema.md for complete PRD JSON schema documentation.
