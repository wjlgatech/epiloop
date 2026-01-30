# Self-Improvement Pipeline Test Requirements

## Overview

This document describes the requirements and setup for testing the claude-loop self-improvement pipeline integration tests.

## Test Coverage

The `test_self_improvement_e2e.py` file provides comprehensive end-to-end testing for the self-improvement pipeline:

### Test Categories

1. **Full Pipeline Flow** (`TestFullPipeline`)
   - Tests complete flow: log → classify → cluster → analyze → PRD
   - Validates each stage of the pipeline
   - Ensures data flows correctly between modules

2. **PRD Review Workflow** (`TestPRDReviewWorkflow`)
   - Tests PRD approval process
   - Tests PRD rejection with reasons
   - Tests PRD execution workflow
   - Validates status transitions

3. **Validation Suite** (`TestValidationSuite`)
   - Tests that missing tests are detected
   - Tests held-out failure case validation
   - Tests regression detection blocks deployment

4. **Rollback Mechanism** (`TestRollbackMechanism`)
   - Tests rollback data structures
   - Tests PRD status restoration
   - Tests rollback history tracking

5. **Background Daemon** (`TestBackgroundDaemon`)
   - Tests daemon status management
   - Tests lockfile mechanism
   - Tests log threshold triggers
   - Tests graceful shutdown

6. **Mock LLM Integration** (`TestMockLLMIntegration`)
   - Tests deterministic mock LLM responses
   - Tests call counting
   - Tests consistency across runs

7. **E2E Scenarios** (`TestE2EScenarios`)
   - Tests realistic UI automation gap detection
   - Tests transient error handling (should NOT create PRDs)

## Requirements

### Python Version

- Python 3.9 or higher

### Dependencies

```bash
# Core testing framework
pytest>=7.0.0
pytest-cov>=4.0.0  # Optional: for coverage reports

# No other dependencies required - tests use only stdlib and existing modules
```

### Environment Setup

```bash
# Install pytest if not already installed
pip install pytest pytest-cov

# Or use the project's virtual environment
source .venv/bin/activate
pip install pytest pytest-cov
```

## Running Tests

### Basic Test Execution

```bash
# Run all self-improvement E2E tests
pytest tests/test_self_improvement_e2e.py -v

# Run specific test class
pytest tests/test_self_improvement_e2e.py::TestFullPipeline -v

# Run specific test
pytest tests/test_self_improvement_e2e.py::TestFullPipeline::test_full_pipeline_from_logs_to_prd -v

# Run with coverage
pytest tests/test_self_improvement_e2e.py --cov=lib --cov-report=term-missing
```

### CI Mode

For CI environments without external dependencies:

```bash
# Set CI environment variable
CI=true pytest tests/test_self_improvement_e2e.py -v

# CI mode will:
# - Skip tests requiring external tools (pytest, git)
# - Use mock LLM responses only
# - Not make network calls
# - Use temporary directories for isolation
```

### Verbose Output

```bash
# Show stdout/stderr
pytest tests/test_self_improvement_e2e.py -v -s

# Show test durations
pytest tests/test_self_improvement_e2e.py --durations=10

# Stop on first failure
pytest tests/test_self_improvement_e2e.py -x
```

## Test Data

### Sample Execution Logs

Tests use predefined sample logs (`SAMPLE_LOGS`) covering:

- **UI element not found errors** (3 similar failures) → should cluster
- **Network timeout error** (1 transient) → should NOT create PRD
- **Successful execution** (1 success) → should classify as SUCCESS

### Mock LLM Responses

Mock LLM provides deterministic responses for:

- **Root cause analysis**: 5-Whys decomposition
- **Capability gap identification**: UI_INTERACTION category
- **Counterfactual analysis**: "What capability would prevent this?"

### Test Filesystem Structure

Tests create temporary directories with this structure:

```
/tmp/claude_loop_test_XXXXX/
└── .claude-loop/
    ├── execution_log.jsonl          # Execution logs
    ├── capability_gaps.json          # Discovered gaps
    ├── capability_inventory.json     # Available capabilities
    ├── improvements/                 # Generated PRDs
    │   └── improvement-*.json
    ├── analysis_cache/               # Cached root cause analyses
    ├── held_out_cases/               # Validation test cases
    ├── validation_reports/           # Validation results
    ├── daemon_status.json            # Daemon state
    ├── daemon.lock                   # Daemon lockfile
    └── improvement_history.jsonl     # Audit trail
```

## Expected Test Outcomes

### Successful Test Run

```
tests/test_self_improvement_e2e.py::TestFullPipeline::test_full_pipeline_from_logs_to_prd PASSED
tests/test_self_improvement_e2e.py::TestPRDReviewWorkflow::test_approve_prd_workflow PASSED
tests/test_self_improvement_e2e.py::TestPRDReviewWorkflow::test_reject_prd_workflow PASSED
tests/test_self_improvement_e2e.py::TestPRDReviewWorkflow::test_execute_approved_prd PASSED
tests/test_self_improvement_e2e.py::TestPRDReviewWorkflow::test_cannot_execute_unapproved_prd PASSED
tests/test_self_improvement_e2e.py::TestValidationSuite::test_validation_detects_missing_tests PASSED
tests/test_self_improvement_e2e.py::TestValidationSuite::test_validation_with_held_out_cases PASSED
tests/test_self_improvement_e2e.py::TestValidationSuite::test_validation_blocks_on_regression PASSED
tests/test_self_improvement_e2e.py::TestRollbackMechanism::test_rollback_data_structure PASSED
tests/test_self_improvement_e2e.py::TestRollbackMechanism::test_rollback_restores_prd_status PASSED
tests/test_self_improvement_e2e.py::TestRollbackMechanism::test_rollback_history_tracking PASSED
tests/test_self_improvement_e2e.py::TestBackgroundDaemon::test_daemon_status_file_structure PASSED
tests/test_self_improvement_e2e.py::TestBackgroundDaemon::test_daemon_lockfile_mechanism PASSED
tests/test_self_improvement_e2e.py::TestBackgroundDaemon::test_daemon_log_threshold_trigger PASSED
tests/test_self_improvement_e2e.py::TestBackgroundDaemon::test_daemon_runs_without_blocking PASSED
tests/test_self_improvement_e2e.py::TestBackgroundDaemon::test_daemon_graceful_shutdown PASSED
tests/test_self_improvement_e2e.py::TestMockLLMIntegration::test_mock_llm_for_root_cause_analysis PASSED
tests/test_self_improvement_e2e.py::TestMockLLMIntegration::test_mock_llm_call_counting PASSED
tests/test_self_improvement_e2e.py::TestMockLLMIntegration::test_deterministic_results_across_runs PASSED
tests/test_self_improvement_e2e.py::TestE2EScenarios::test_scenario_ui_automation_gap_to_prd PASSED
tests/test_self_improvement_e2e.py::TestE2EScenarios::test_scenario_transient_error_not_creating_prd PASSED

======================= 21 passed in 2.54s =======================
```

### Coverage Report

```bash
pytest tests/test_self_improvement_e2e.py --cov=lib --cov-report=html

# Generates htmlcov/index.html with coverage details
```

Expected coverage targets:
- `failure-classifier.py`: >80%
- `pattern-clusterer.py`: >75%
- `root-cause-analyzer.py`: >70% (LLM mocking reduces coverage)
- `gap-generalizer.py`: >75%
- `improvement-prd-generator.py`: >70%
- `improvement-validator.py`: >70%

## Test Isolation

### Filesystem Isolation

- Each test class uses a unique temporary directory
- Cleanup happens automatically via `tearDownClass()`
- No shared state between test classes

### Environment Isolation

- `CLAUDE_LOOP_DIR` environment variable points to test directory
- Original environment restored after tests
- No modifications to actual `.claude-loop/` directory

### Mock Isolation

- Mock LLM responses are deterministic
- No actual LLM API calls made
- No network dependencies

## Debugging Failed Tests

### Common Issues

1. **Import Errors**
   ```
   ImportError: Cannot import failure_classifier
   ```
   **Solution**: Ensure `lib/` directory is in path and all modules exist

2. **File Not Found**
   ```
   FileNotFoundError: execution_log.jsonl
   ```
   **Solution**: Check that `setUp()` creates necessary files

3. **Assertion Failures**
   ```
   AssertionError: Expected 3 patterns, got 1
   ```
   **Solution**: Check `min_occurrences` threshold and sample data

### Debug Mode

```bash
# Run with Python debugger
pytest tests/test_self_improvement_e2e.py --pdb

# Run with verbose logging
pytest tests/test_self_improvement_e2e.py -v -s --log-cli-level=DEBUG
```

### Inspect Test Directory

```bash
# Keep test directory after failure
pytest tests/test_self_improvement_e2e.py --basetemp=/tmp/pytest-debug

# Then inspect:
ls -la /tmp/pytest-debug/test_*/
cat /tmp/pytest-debug/test_*/.claude-loop/execution_log.jsonl
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Test Self-Improvement Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install pytest pytest-cov

      - name: Run E2E tests
        env:
          CI: true
        run: |
          pytest tests/test_self_improvement_e2e.py -v --cov=lib --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run self-improvement tests before commit
pytest tests/test_self_improvement_e2e.py -x -q

if [ $? -ne 0 ]; then
    echo "Self-improvement tests failed. Commit aborted."
    exit 1
fi
```

## Performance Expectations

### Test Execution Time

- Full suite: ~2-5 seconds
- Individual test: ~100-500ms
- Mock LLM adds minimal overhead (<10ms per call)

### Resource Usage

- Memory: <100MB
- Disk: <10MB for temporary files
- CPU: Minimal (no heavy computation)

## Extending Tests

### Adding New Test Cases

1. **Add test data to `SAMPLE_LOGS`**:
   ```python
   SAMPLE_LOGS.append({
       "story_id": "TEST-006",
       "error_type": "your_error_type",
       # ... other fields
   })
   ```

2. **Create test method**:
   ```python
   def test_your_scenario(self):
       """Test description."""
       self.write_execution_logs([SAMPLE_LOGS[5]])
       # ... test logic
       self.assertEqual(expected, actual)
   ```

3. **Add mock LLM response if needed**:
   ```python
   mock_llm.responses["your_scenario"] = MockLLMResponse(
       analysis=json.dumps({...}),
       confidence=0.8
   )
   ```

### Adding New Test Classes

```python
class TestYourFeature(SelfImprovementE2ETestCase):
    """Test your feature."""

    def test_something(self):
        """Test something specific."""
        # Inherits setUp/tearDown and temp directory
        pass
```

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Possible Causes**:
- CI mode detection (`self.is_ci` flag)
- Tool availability (`shutil.which("pytest")`)
- File permissions

**Solution**: Check CI-specific code paths and mock appropriately

### Tests Fail Due to Timing

**Possible Causes**:
- Timestamp-based assertions
- Race conditions in daemon tests

**Solution**: Use fixed timestamps in test data or add tolerances

### Module Import Errors

**Possible Causes**:
- Hyphenated filenames (`failure-classifier.py`)
- Missing `__init__.py` files

**Solution**: Use `_import_module()` helper for hyphenated names

## Support

For issues or questions:
1. Check this document
2. Review test code comments
3. Run with `-v -s` for verbose output
4. File an issue with test failure details

## Future Improvements

Potential enhancements to test suite:

- [ ] Add performance benchmarks
- [ ] Add stress tests (1000+ log entries)
- [ ] Add concurrent execution tests
- [ ] Add test data generators
- [ ] Add visual test reports
- [ ] Add mutation testing
- [ ] Add property-based testing (hypothesis)
