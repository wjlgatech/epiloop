# Contributing to claude-loop

Thank you for your interest in contributing to claude-loop! This document outlines
the contribution process, with special attention to our core file protection policy.

## Table of Contents

- [Core File Protection](#core-file-protection)
- [Contribution Workflow](#contribution-workflow)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)

## Core File Protection

### Overview

claude-loop implements strict immutability rules for foundational files. This ensures
system stability and prevents automated processes from accidentally breaking core
functionality.

**Key Principle: Core files require manual human commits. No automated modifications allowed.**

### Protected Files

The following files are protected by `lib/core-protection.py`:

#### Immutable Core (Cannot be unprotected)

These files form the foundation of claude-loop and can NEVER be modified by automation:

| File | Purpose |
|------|---------|
| `claude-loop.sh` | Main orchestration script |
| `lib/core-protection.py` | Self-protection (prevents circumvention) |
| `lib/execution-logger.sh` | Execution audit trail |

#### Protected Core

These files are protected by default but can be unprotected if necessary:

| File | Purpose |
|------|---------|
| `lib/prd-parser.sh` | PRD schema validation |
| `lib/monitoring.sh` | Cost and metrics tracking |
| `lib/worker.sh` | Worker process isolation |
| `lib/parallel.sh` | Parallel execution |
| `lib/merge-controller.py` | Git merge management |
| `prompt.md` | Iteration prompt template |
| `AGENTS.md` | Pattern documentation |

#### Security-Sensitive Patterns

These patterns are always protected for security:

- `.env`, `.env.*` - Environment variables
- `*.pem`, `*.key` - Cryptographic keys
- `**/secrets/**` - Secrets directories
- `**/credentials*` - Credential files

### Modifying Core Files

If you need to modify a core file, follow this process:

#### Step 1: Create an Issue

Create a GitHub issue explaining:
- Which core file(s) need modification
- Why the modification is necessary
- What changes you propose
- Impact analysis (what could break)

#### Step 2: Discussion and Approval

Core modifications require:
- Discussion with maintainers
- Review of impact analysis
- Explicit approval from at least one maintainer

#### Step 3: Manual Implementation

Once approved:

```bash
# 1. Create a feature branch
git checkout -b core/your-change-description

# 2. Make your changes manually
# (claude-loop automation will refuse to modify these files)

# 3. Verify the changes
python lib/core-protection.py check your-file.sh

# 4. Run the full test suite
pytest tests/

# 5. Commit with clear message
git commit -m "core: description of change

Approved in issue #XXX
Manual implementation required due to core file protection.

Co-Authored-By: Your Name <your@email.com>"

# 6. Push and create PR
git push -u origin core/your-change-description
```

#### Step 4: Review Process

Core file PRs receive extra scrutiny:
- All CI checks must pass
- Minimum 2 reviewer approvals required
- Maintainer final approval required
- 24-hour cool-off period before merge

### Why These Restrictions?

1. **Stability**: Core files are the foundation. Breaking them breaks everything.
2. **Security**: Automated modification of core files could be exploited.
3. **Auditability**: Manual commits create clear audit trail.
4. **Reversibility**: Human review catches issues before they're committed.

### Checking Protection Status

```bash
# List all protected files
python lib/core-protection.py list

# Check if a specific file is protected
python lib/core-protection.py check lib/worker.sh

# View access audit log
python lib/core-protection.py audit

# Validate a set of changes (useful for CI)
python lib/core-protection.py validate-changes file1.py file2.sh
```

### Adding/Removing Protection

To add a file to protection:
```bash
python lib/core-protection.py add path/to/file.py \
    --reason "Critical configuration file" \
    --confirm
```

To remove protection (for non-immutable files only):
```bash
python lib/core-protection.py remove path/to/file.py --confirm
```

Note: Immutable core files (`claude-loop.sh`, `lib/core-protection.py`,
`lib/execution-logger.sh`) can NEVER be removed from protection.

## Contribution Workflow

### For Non-Core Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Commit with clear message
6. Push and create PR

### For Core Changes

Follow the [Modifying Core Files](#modifying-core-files) process above.

### For Improvement Proposals

claude-loop has a self-improvement system that generates improvement proposals.
These proposals:
- Are queued for human review (never auto-implemented)
- Are automatically rejected if they affect core files
- Require explicit human approval before implementation

To review proposals:
```bash
python lib/improvement-queue.py queue list
python lib/improvement-queue.py queue review <proposal-id>
```

## Code Style

### Python

- Follow PEP 8
- Use type hints for all function signatures
- Add docstrings to all public functions and classes
- Use `dataclasses` for data structures
- Maximum line length: 100 characters

### Bash

- Use `#!/usr/bin/env bash` shebang
- Quote all variables: `"$variable"`
- Use `[[` instead of `[` for conditionals
- Add comments for non-obvious logic

### General

- Prefer explicit over implicit
- No secrets or credentials in code
- Use meaningful variable/function names
- Add tests for new functionality

## Testing Requirements

### Before Submitting PR

1. **All tests pass**: `pytest tests/`
2. **Type checking passes**: `pyright lib/` (warnings for optional imports OK)
3. **No new linting errors**
4. **Core protection validated**: `python lib/core-protection.py validate-changes <changed-files>`

### Test Coverage

- New features should include tests
- Bug fixes should include regression tests
- Target: >85% coverage for new modules

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_core_protection.py

# Run with coverage
pytest tests/ --cov=lib --cov-report=html
```

## Pull Request Process

1. **Fill out PR template completely**
2. **Link related issues**
3. **Ensure CI passes**
4. **Request review from appropriate reviewers**
5. **Address review feedback**
6. **Wait for approval** (2 approvals for core changes)
7. **Squash and merge** (or rebase for core changes)

### PR Title Format

- `feat: Add new feature`
- `fix: Fix bug in X`
- `docs: Update documentation`
- `core: Modify core file X` (requires special approval)
- `chore: Update dependencies`
- `test: Add tests for X`

### Commit Message Format

```
type(scope): short description

Longer description if needed.

- Bullet points for multiple changes
- Reference issues with #XXX

Co-Authored-By: Name <email>
```

## Questions?

- Open a GitHub issue for questions
- Tag maintainers for urgent items
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the
same license as the project.

---

Thank you for contributing to claude-loop!
