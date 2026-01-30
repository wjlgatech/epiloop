# Claude-Loop Test Suite

This directory contains test suites for validating claude-loop's functionality.

## Test Files

### test_failure_classification.py

Classification Accuracy Validator (SI-013) - Tests the accuracy of the failure classifier against manually labeled ground truth.

**Purpose**: Validate that the failure classifier can accurately categorize failures into SUCCESS, TASK_FAILURE, CAPABILITY_GAP, and TRANSIENT_ERROR with >80% accuracy before enabling autonomous PRD generation.

**Test Coverage**:
- 24 manually labeled test cases across all 4 categories
- Measures overall accuracy, precision, recall, and F1 score per category
- Generates confusion matrix visualization
- Tracks accuracy over time
- Alerts if accuracy drops below threshold

**Current Performance**:
- Overall Accuracy: **95.83%** (23/24 correct)
- Per-Category Metrics:
  - CAPABILITY_GAP: 90.91% (10/11)
  - SUCCESS: 100% (2/2)
  - TASK_FAILURE: 100% (5/5)
  - TRANSIENT_ERROR: 100% (6/6)

### fixtures/labeled_failures.json

Ground truth data for classification validation. Contains 24 test cases with manually verified classifications.

## Running Tests

### Run all classification tests:
```bash
pytest tests/test_failure_classification.py -v
```

### Run specific test:
```bash
pytest tests/test_failure_classification.py::test_classification_accuracy -v
```

### Run with output (see metrics):
```bash
pytest tests/test_failure_classification.py -v -s
```

### Run accuracy validation only:
```bash
pytest tests/test_failure_classification.py::test_classification_accuracy -v -s
```

### Generate detailed report:
```bash
pytest tests/test_failure_classification.py --accuracy-report -v -s
```

## Test Outputs

Tests generate several files in `.claude-loop/`:

- `confusion_matrix.json` - Confusion matrix data
- `accuracy_history.jsonl` - Accuracy tracking over time
- `accuracy_alerts.log` - Log of accuracy drops below threshold
- `classification_report.txt` - Detailed classification report (with --accuracy-report flag)

## Accuracy Threshold

**Requirement**: >80% accuracy for autonomous PRD generation

**Current Status**: ✅ **95.83%** - Well above threshold

**Alert Threshold**: 70% - Tests will alert if accuracy drops below this level

## Adding New Test Cases

To add new labeled test cases:

1. Edit `tests/fixtures/labeled_failures.json`
2. Add a new test case with:
   - Unique `id` (e.g., "TC-025")
   - Manual `ground_truth` classification
   - Complete `log_entry` with all required fields
3. Run tests to validate: `pytest tests/test_failure_classification.py -v`
4. Verify accuracy remains >80%

## Continuous Monitoring

The test suite tracks accuracy over time in `accuracy_history.jsonl`. Each test run appends a new entry with:
- Timestamp
- Overall accuracy
- Per-category accuracy
- Test count

This enables detection of:
- Accuracy regressions after classifier changes
- Patterns in misclassifications
- Need for additional test cases

## Integration with Self-Improvement

The Classification Accuracy Validator (SI-013) is a **gate** for autonomous PRD generation:

- ✅ **SI-013 passes (95.83% accuracy)** → Safe to enable autonomous improvements
- ❌ **Accuracy <80%** → Autonomous mode blocked until classifier improves

See `prd-self-improvement.json` for the full self-improvement pipeline.

---

# Phase 2 Integration Tests (US-008)

Comprehensive testing for Phase 2 features: MCP, Multi-Provider LLM, and Bounded Delegation.

## Phase 2 Test Organization

```
tests/
├── Phase 2 Individual Feature Tests
│   ├── mcp_test.sh                     # MCP integration (13 tests)
│   ├── multi_provider_test.sh          # Multi-provider LLM (15 tests)
│   └── delegation_test.sh              # Bounded delegation (35+ tests)
│
└── Phase 2 Integration Tests
    └── phase2_integration_test.sh      # Comprehensive integration suite
        ├── Individual feature tests    # (3 test categories)
        ├── Combined feature tests      # (4 test categories)
        ├── Performance tests           # (4 test categories)
        ├── Rollback tests              # (5 test categories)
        └── Error injection tests       # (4 test categories)
```

## Running Phase 2 Tests

### Quick Start

```bash
# Run all Phase 2 tests
make test-phase2

# Run quick individual feature tests
./tests/mcp_test.sh
./tests/multi_provider_test.sh
./tests/delegation_test.sh

# Run comprehensive integration tests
./tests/phase2_integration_test.sh
```

### Makefile Targets

```bash
make test-phase2        # All Phase 2 tests
make test-individual    # Individual features only
make test-combined      # Combined feature tests
make test-performance   # Performance tests
make test-rollback      # Rollback tests
make test-error         # Error injection tests
```

### Direct Execution

```bash
# Run all integration tests
./tests/phase2_integration_test.sh

# Run with verbose output
./tests/phase2_integration_test.sh --verbose

# Run specific category
./tests/phase2_integration_test.sh --category combined
./tests/phase2_integration_test.sh --category performance
./tests/phase2_integration_test.sh --category rollback
./tests/phase2_integration_test.sh --category error_injection
```

## Test Categories

### 1. Individual Feature Tests

**MCP Integration (13 tests)**
- Bridge script exists and sourceable
- Functions available (init, list_tools, call_tool)
- Disabled by default (feature flag)
- Config example valid JSON
- Client executable and provides help
- Parse MCP call from prompt

**Multi-Provider LLM (15 tests)**
- Provider list shows configured providers
- Complexity-based routing (cheap/medium/powerful)
- Capability filtering (vision, tools)
- Fallback chain
- Selection speed (<50ms)
- Cost tracking and reporting

**Bounded Delegation (35+ tests)**
- Delegation syntax parsing
- Depth limit enforcement (MAX=2)
- Cycle detection
- Context budget validation (<100k tokens)
- Git worktree isolation
- Cost attribution

### 2. Combined Feature Tests (4 tests)

- MCP + Multi-Provider
- Delegation + Multi-Provider
- All features enabled
- No conflicts between features

### 3. Performance Tests (4 tests)

- Total overhead < 5%
- MCP call latency < 500ms
- Provider selection < 50ms
- Delegation parsing < 10ms

### 4. Rollback Tests (5 tests)

- Disable MCP feature
- Disable Multi-Provider feature
- Disable Delegation feature
- Disable all features
- Phase 1 fallback verification

### 5. Error Injection Tests (4 tests)

- MCP server unavailable (graceful failure)
- Provider API failure (fallback)
- Delegation context overflow (budget check)
- Invalid config handling

## Coverage Requirements

**US-008 Acceptance Criteria**: >90% coverage for Phase 2 features

**Total Tests**: 83+ tests across all categories
- Individual: 63+ tests
- Integration: 20+ tests

## Performance Thresholds

| Metric | Threshold | Test |
|--------|-----------|------|
| Total overhead | <5% | Total overhead vs Phase 1 |
| MCP latency | <500ms | MCP initialization time |
| Provider selection | <50ms | Selection time measurement |
| Delegation parsing | <10ms | Parser execution time |

## Troubleshooting

**Tests fail with "MCP library not installed"**
```bash
pip install -r requirements.txt
```

**Permission denied on test scripts**
```bash
chmod +x tests/*.sh
```

**Git worktree errors**
```bash
git worktree prune
make clean
```

**bc command not found (macOS)**
```bash
brew install bc
```

## Documentation

- **MCP Integration**: `docs/features/mcp-integration.md`
- **Multi-Provider**: `docs/features/multi-provider-llm.md`
- **Delegation**: `docs/features/bounded-delegation.md`
- **Phase 2 PRD**: `prds/phase2-tier2-library-integration.json`

## Contributing

When adding Phase 2 features:
1. Write tests first (TDD)
2. Ensure >90% coverage
3. Update test categories
4. Add to Makefile
5. Run full suite before committing

```bash
# Full test run
make test-all
```
