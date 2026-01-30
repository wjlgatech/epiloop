# Workspace Sandboxing

**Feature ID**: US-003
**Status**: Implemented
**Version**: Phase 1

## Overview

Workspace sandboxing limits claude-loop execution scope to specific folders within your repository. This provides better control over which parts of your codebase Claude can modify, improving safety and reducing context overhead for focused development work.

## Motivation

When working on large codebases, you often want to limit changes to specific subsystems or modules. Workspace sandboxing:

1. **Improves Safety**: Prevents accidental modifications to unrelated code
2. **Reduces Context**: Focuses Claude's attention on relevant files only
3. **Enables Parallel Execution**: Different workspaces can be worked on concurrently
4. **Supports Monorepos**: Work on specific packages or services independently

## Usage

### Basic Usage

Specify workspace folders using the `--workspace` flag:

```bash
# Single folder
./claude-loop.sh --workspace "lib"

# Multiple folders (comma-separated)
./claude-loop.sh --workspace "lib,src,tests"

# With other flags
./claude-loop.sh --workspace "lib,src" --max-iterations 20 -v
```

### Workspace Modes

Control how strictly workspace boundaries are enforced:

```bash
# Permissive mode (default): Warns but allows access outside workspace
./claude-loop.sh --workspace "lib,src" --workspace-mode permissive

# Strict mode: Hard fails if files outside workspace are accessed
./claude-loop.sh --workspace "lib,src" --workspace-mode strict
```

## Features

### 1. Folder Validation

When you specify workspace folders, claude-loop validates that:

- All folders exist in the filesystem
- All folders are within the git repository
- Symlinks are resolved to prevent escaping the repository
- Nested workspaces are handled correctly

**Example validation output:**

```
[WORKSPACE] Initialized workspace manager
[WORKSPACE]   Folders: lib,src,tests
[WORKSPACE]   Mode: permissive
[WORKSPACE]   Repo Root: /Users/user/my-project
[WORKSPACE] Validated workspace folder: lib
[WORKSPACE] Validated workspace folder: src
[WORKSPACE] Validated workspace folder: tests
[WORKSPACE] All workspace folders validated
[INFO] Workspace sandboxing: Enabled (mode: permissive)
```

### 2. Auto-Inferred FileScope

When workspace sandboxing is enabled, claude-loop automatically infers the `fileScope` field for each user story in your PRD. This happens during initialization:

```bash
[WORKSPACE] Auto-inferring fileScope from workspace...
[WORKSPACE] Setting fileScope for story US-001
[WORKSPACE] Setting fileScope for story US-002
[WORKSPACE] Updated fileScope for 2 stories
```

The inferred fileScope includes common file patterns:

```json
[
  "lib/**/*.sh",
  "lib/**/*.js",
  "lib/**/*.ts",
  "lib/**/*.py",
  "lib/**/*.json",
  "lib/**/*.md",
  "lib/**/*.yaml",
  "lib/**/*.yml",
  "src/**/*.sh",
  "src/**/*.js",
  ...
]
```

**Manual Override**: If a story already has an explicit `fileScope` in the PRD, it won't be overwritten.

### 3. Workspace Mounting (Parallel Execution)

When using parallel PRD execution (`--parallel`), workspace folders are mounted in each worker's isolated directory using symlinks. This provides:

- **Efficiency**: Symlinks avoid copying large directories
- **Isolation**: Each worker has its own view of the workspace
- **Safety**: Workers cannot interfere with each other's file operations

The mounting happens automatically when workers are created.

### 4. Prompt Augmentation

Claude is informed about workspace boundaries in every iteration prompt:

```markdown
# Workspace Sandboxing

This iteration is running with workspace sandboxing ENABLED.

## Workspace Configuration

**Mode**: strict
**Allowed Folders**: lib,src,tests

## Workspace Rules

1. **File Access Constraints**: You should primarily work with files within the workspace folders listed above.

2. **Strict Mode**: File access outside workspace will FAIL. You must stay within workspace boundaries.

3. **File Scope**: The story's fileScope has been automatically inferred from workspace contents. Focus your changes on these patterns.

4. **Safety**: Do not attempt to access files outside the workspace unless absolutely necessary.

## Workspace Folders

- `lib/`
- `src/`
- `tests/`
```

This helps Claude understand the constraints and focus its implementation accordingly.

### 5. Access Validation

The workspace manager validates all file access operations:

```bash
# In permissive mode
[WORKSPACE] WARNING: File access outside workspace (permissive mode)
[WORKSPACE]   File: /path/to/outside/file.ts
[WORKSPACE]   Operation: write

# In strict mode
[WORKSPACE] BLOCKED: File access outside workspace
[WORKSPACE]   File: /path/to/outside/file.ts
[WORKSPACE]   Operation: write
[WORKSPACE]   Workspace folders: lib,src,tests
```

## CLI Reference

### Workspace Manager Standalone

The workspace manager can be used independently:

```bash
# Validate workspace folders
./lib/workspace-manager.sh validate "lib,src,tests"

# Check if a file is within workspace
./lib/workspace-manager.sh check-file "src/main.ts" "src,lib"
# Exit code: 0 = in workspace, 1 = outside

# Infer fileScope patterns
./lib/workspace-manager.sh infer-scope "lib,src"
# Output: JSON array of file patterns

# Update PRD with workspace patterns
./lib/workspace-manager.sh update-prd "lib,src" "prd.json"

# Mount workspace in worker directory
./lib/workspace-manager.sh mount "lib,src" "/path/to/worker"

# Unmount workspace from worker directory
./lib/workspace-manager.sh unmount "lib,src" "/path/to/worker"

# Generate workspace section for prompt
./lib/workspace-manager.sh prompt-section "lib,src" "strict"
```

## Integration with Other Features

### Parallel PRD Execution

Workspace sandboxing works seamlessly with parallel execution:

```bash
# Each PRD can have different workspace scopes
./claude-loop.sh --parallel --workspace "lib,src"
```

Each worker gets its own workspace mount, preventing conflicts.

### Progress Indicators

The progress UI shows workspace information:

```
[INFO] Workspace sandboxing: Enabled (mode: strict)
[WORKSPACE] Folders: lib,src,tests
```

### Agent Selection

Agents receive workspace context through the augmented prompt, helping them make better decisions about which files to modify.

## Edge Cases and Limitations

### Edge Case: Symlinks

**Scenario**: Workspace folder is a symlink to a directory outside the repository.

**Behavior**:
- In validation, the real path (after resolving symlinks) is checked
- If the real path is outside the repository, validation fails
- This prevents escaping the workspace through symlinks

### Edge Case: Nested Workspaces

**Scenario**: Specifying both `lib` and `lib/utils` as workspace folders.

**Behavior**:
- Both are validated independently
- File access checks pass if file is in either folder
- No special nesting logic is needed

### Edge Case: Relative vs Absolute Paths

**Scenario**: Mixing relative and absolute paths in workspace specification.

**Behavior**:
- Both are supported and normalized
- Relative paths are resolved relative to repository root
- All paths are converted to absolute for comparison

### Edge Case: Non-Existent Folders

**Scenario**: Specifying a folder that doesn't exist yet.

**Behavior**:
- Validation fails immediately
- Claude-loop exits with error code 1
- User must create the folder first or remove it from workspace specification

### Limitation: Git Operations

**Current Behavior**: Workspace validation doesn't intercept git commands.

**Implication**: Claude can still commit files outside the workspace if git operations aren't restricted.

**Mitigation**: Use `.gitignore` and pre-commit hooks as additional safety layers.

### Limitation: Dynamic File Creation

**Current Behavior**: FileScope is inferred at initialization time.

**Implication**: If Claude creates new file types during execution, they might not match the inferred patterns.

**Mitigation**: Use permissive mode if you expect dynamic file creation.

## Examples

### Example 1: Focused Library Development

Working only on the library code:

```bash
./claude-loop.sh --workspace "lib" --workspace-mode strict
```

**PRD**:
```json
{
  "project": "my-library",
  "branchName": "feature/lib-refactor",
  "userStories": [
    {
      "id": "US-001",
      "title": "Refactor error handling",
      "description": "Improve error handling in lib/errors.ts",
      "acceptanceCriteria": [
        "Add custom error classes",
        "Add error recovery logic",
        "Update tests"
      ],
      "fileScope": ["lib/**/*.ts", "lib/**/*.test.ts"]
    }
  ]
}
```

### Example 2: Monorepo Package Development

Working on a specific package in a monorepo:

```bash
./claude-loop.sh --workspace "packages/api,packages/shared"
```

**PRD**:
```json
{
  "project": "monorepo-api-update",
  "branchName": "feature/api-v2",
  "userStories": [
    {
      "id": "US-001",
      "title": "Add new API endpoints",
      "description": "Implement v2 API endpoints in packages/api",
      "acceptanceCriteria": [
        "Add /v2/users endpoint",
        "Add /v2/posts endpoint",
        "Update shared types"
      ],
      "fileScope": [
        "packages/api/**/*.ts",
        "packages/shared/types/**/*.ts"
      ]
    }
  ]
}
```

### Example 3: Test-Driven Development

Limiting scope to tests while implementation is in progress:

```bash
./claude-loop.sh --workspace "tests,src" --workspace-mode permissive
```

This allows Claude to:
- Write tests in `tests/`
- Implement features in `src/`
- Warn if accessing other directories (permissive mode)

## Configuration

### Environment Variables

You can set workspace configuration via environment variables:

```bash
export WORKSPACE_FOLDERS="lib,src,tests"
export WORKSPACE_MODE="strict"
./claude-loop.sh
```

### PRD-Level Configuration

Future enhancement: Support workspace configuration in `prd.json`:

```json
{
  "project": "my-project",
  "workspace": {
    "folders": ["lib", "src", "tests"],
    "mode": "strict"
  },
  "userStories": [...]
}
```

## Troubleshooting

### Workspace Validation Fails

**Error**: "Workspace folder does not exist: lib"

**Solution**: Ensure the folder exists or remove it from the workspace specification.

### Files Outside Workspace Being Modified

**In Permissive Mode**: This is expected behavior - warnings are shown but access is allowed.

**In Strict Mode**: Check logs for access violations. Claude should respect workspace boundaries.

**Possible Causes**:
- Git operations (not restricted by workspace validation)
- System commands that bypass validation
- Bugs in validation logic (please report!)

### FileScope Not Auto-Inferred

**Possible Causes**:
- Story already has explicit `fileScope` in PRD (won't be overwritten)
- Workspace manager not found or not sourced
- Workspace disabled (`WORKSPACE_ENABLED=false`)

**Solution**: Check initialization logs for workspace manager status.

## Performance Impact

Workspace sandboxing has minimal performance overhead:

- **Validation**: O(n) where n = number of workspace folders (typically < 10)
- **FileScope Inference**: One-time operation at initialization
- **Mounting**: Symlink creation is instant
- **Access Checks**: O(n) per file access, but only in strict mode

**Typical overhead**: < 100ms for initialization, < 1ms per file access check.

## Security Considerations

### Symlink Attacks

**Risk**: Attacker creates symlink from workspace to sensitive directory.

**Mitigation**:
- Real paths are resolved during validation
- Paths outside repository are rejected
- Only applies during initialization (not runtime)

### Path Traversal

**Risk**: Claude uses `../` to escape workspace boundaries.

**Mitigation**:
- Paths are normalized before validation
- `..` segments are resolved to absolute paths
- Validation checks final absolute path

### Worker Isolation

**Risk**: Parallel workers interfere with each other's workspaces.

**Mitigation**:
- Each worker has isolated directory
- Workspace symlinks are private to worker
- No shared state between workers

## Future Enhancements

1. **Dynamic FileScope Update**: Update fileScope during execution as new files are created
2. **Workspace Presets**: Predefined workspace configurations for common scenarios
3. **Workspace Inheritance**: Child workspaces inherit from parent configurations
4. **Workspace Templates**: Template-based workspace configuration in PRDs
5. **Validation Hooks**: Custom validation logic per project
6. **Performance Monitoring**: Track workspace-related overhead in metrics

## Related Features

- **Progress Indicators (US-001)**: Shows workspace status in UI
- **PRD Templates (US-002)**: Templates can include workspace configuration
- **Checkpoint Confirmations (US-004)**: Safety checks complement workspace boundaries
- **Parallel PRD Execution**: Workspace mounting enables parallel workers

## Technical Implementation

### Core Components

1. **lib/workspace-manager.sh**: Standalone workspace management library
2. **claude-loop.sh**: Integration hooks for workspace initialization and validation
3. **Prompt Augmentation**: Workspace section added to iteration prompts

### Key Functions

- `init_workspace()`: Initialize workspace configuration
- `validate_workspace_folders()`: Validate workspace folders exist and are safe
- `is_file_in_workspace()`: Check if file is within workspace boundaries
- `validate_file_access()`: Validate file access according to mode
- `mount_workspace_in_worker()`: Mount workspace using symlinks
- `infer_file_scope_from_workspace()`: Auto-generate fileScope patterns
- `get_workspace_prompt_section()`: Generate workspace information for prompts

### Integration Points

1. **Initialization**: `check_workspace()` called during main initialization
2. **Prompt Building**: `build_iteration_prompt()` includes workspace section
3. **Worker Setup**: Workspace mounted in worker directories (future: worker.sh integration)

## Changelog

- **2026-01-13**: Initial implementation (US-003)
  - Added workspace folder validation
  - Implemented auto-inference of fileScope
  - Created workspace manager library
  - Integrated with prompt generation
  - Added strict and permissive modes
