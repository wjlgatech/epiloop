# Benchmark Tasks - Tier 1 Validation

This directory contains the benchmark infrastructure for validating claude-loop performance against alternatives (baseline Claude Code CLI, agent-zero).

## Overview

The Tier 1 validation executes 3 real-world tasks across 3 subjects:
1. **Baseline** (Claude Code CLI) - Direct CLI usage
2. **claude-loop** - Quick task mode execution
3. **agent-zero** - Agent-zero framework execution

## Directory Structure

```
benchmark-tasks/
├── benchmark_runner.py   # Main benchmark orchestrator
├── tasks/                # Task definitions (YAML/JSON)
│   ├── TASK-001.yaml    # Token optimization task
│   ├── TASK-002.yaml    # Health check API task
│   └── TASK-003.yaml    # Job locking task
├── validation/           # Task-specific validators (US-004)
├── results/              # Execution results (JSON)
└── README.md             # This file
```

## Installation

### Prerequisites

1. **Python 3.8+**
2. **PyYAML**: `pip install pyyaml`
3. **Claude Code CLI**: Install from https://github.com/anthropics/claude-code
4. **API Keys**: Set `ANTHROPIC_API_KEY` environment variable

### Optional

- **claude-loop**: For running claude-loop adapter (US-002)
- **agent-zero**: For running agent-zero adapter (US-003)

## Usage

### Running a Single Task

```bash
# Execute TASK-001 with baseline adapter
python3 benchmark_runner.py \
  --task tasks/TASK-001.yaml \
  --subject baseline \
  --output-dir results \
  --timeout 300
```

### Running All Tasks

```bash
# Execute all tasks in tasks/ directory
python3 benchmark_runner.py \
  --subject baseline \
  --real-execution \
  --output-dir results
```

### Command-Line Options

- `--task PATH`: Path to task definition file
- `--subject {baseline,claude-loop,agent-zero}`: Subject to test
- `--output-dir PATH`: Output directory for results (default: `benchmark-results`)
- `--timeout SECONDS`: Execution timeout (default: 300)
- `--real-execution`: Execute all tasks from `tasks/` directory

## Task Definition Format

Tasks are defined in YAML or JSON format:

```yaml
task_id: TASK-001
title: Task Title
description: |
  Multi-line task description explaining what needs to be done.

acceptance_criteria:
  - "Criterion 1: Specific, testable requirement"
  - "Criterion 2: Another specific requirement"
  - "Criterion 3: Third requirement"

context:
  background: "Why this task is important"
  constraints:
    - "Constraint 1"
    - "Constraint 2"

fileScope:
  - "path/to/file1.py"
  - "path/to/file2.py"
```

## Benchmark Metrics

Each task execution captures:

| Metric | Type | Description |
|--------|------|-------------|
| `success` | boolean | Whether task completed successfully |
| `wall_clock_seconds` | float | Total execution time |
| `total_tokens` | int | Total tokens consumed |
| `estimated_cost_usd` | float | Estimated API cost |
| `criteria_scores` | dict | Acceptance criteria scores (0.0-1.0) |
| `overall_score` | float | Weighted average of criteria scores |
| `error_message` | string | Error details if failed |

## Results Format

Results are saved as JSON files in the output directory:

```json
{
  "task_id": "TASK-001",
  "subject": "baseline",
  "timestamp": 1705628400.0,
  "metrics": {
    "success": true,
    "wall_clock_seconds": 45.2,
    "total_tokens": 5000,
    "estimated_cost_usd": 0.045,
    "criteria_scores": {
      "AC-001": 1.0,
      "AC-002": 0.9,
      "AC-003": 1.0
    },
    "overall_score": 0.97,
    "error_message": null
  }
}
```

## Baseline Adapter Implementation

The `BaselineAdapter` class implements task execution using the Claude Code CLI.

### Key Features

1. **Subprocess Execution**: Invokes `claude` CLI via subprocess
2. **Metrics Capture**: Extracts token usage from CLI output
3. **Timeout Handling**: Enforces execution timeout
4. **Error Handling**: Captures and reports errors clearly
5. **Acceptance Criteria Validation**: Validates task completion

### Example Usage

```python
from benchmark_runner import BaselineAdapter, TaskDefinition

# Load task
task = load_task_definition(Path("tasks/TASK-001.yaml"))

# Execute with baseline adapter
adapter = BaselineAdapter()
metrics = adapter.execute_task(task, timeout_seconds=300)
adapter.cleanup()

# Check results
print(f"Success: {metrics.success}")
print(f"Score: {metrics.overall_score:.2f}")
print(f"Cost: ${metrics.estimated_cost_usd:.4f}")
```

## Testing

Run unit tests to verify baseline adapter functionality:

```bash
python3 -c "
from benchmark_runner import BaselineAdapter, BenchmarkMetrics
import tempfile
from pathlib import Path

# Test adapter instantiation
temp_dir = Path(tempfile.mkdtemp(prefix='test_baseline_'))
adapter = BaselineAdapter(working_dir=temp_dir)
print('✓ Adapter created')

# Test metrics
metrics = BenchmarkMetrics(
    success=True,
    wall_clock_seconds=10.0,
    total_tokens=1000,
    estimated_cost_usd=0.009,
    criteria_scores={'AC-001': 1.0, 'AC-002': 0.9}
)
assert metrics.overall_score > 0.9
print('✓ Metrics validated')

adapter.cleanup()
print('✓ All tests passed')
"
```

## Acceptance Criteria Validation

Currently, the baseline adapter uses simple heuristics for validation:
- If execution succeeds, acceptance criteria are assumed met

**Future Enhancement (US-004)**: Task-specific validators will be implemented in the `validation/` directory to provide rigorous acceptance criteria validation.

## Error Handling

The adapter handles several error scenarios:

1. **Timeout**: Returns metrics with `timeout` error message
2. **CLI Not Found**: Raises `RuntimeError` with installation instructions
3. **Execution Failure**: Captures exit code and stderr
4. **Unexpected Errors**: Catches and reports all exceptions

## Performance Characteristics

- **Startup overhead**: ~1-2 seconds (CLI initialization)
- **Execution time**: Varies by task complexity
- **Token usage**: Depends on task and model
- **Memory usage**: Minimal (~50MB baseline)

## Troubleshooting

### Claude CLI Not Found

```
Error: Claude Code CLI not found. Please install Claude Code CLI first.
Installation: https://github.com/anthropics/claude-code
```

**Solution**: Install Claude Code CLI and ensure it's in your PATH.

### PyYAML Not Found

```
ModuleNotFoundError: No module named 'yaml'
```

**Solution**: Install PyYAML: `pip install pyyaml`

### API Key Not Set

```
Error: ANTHROPIC_API_KEY environment variable not set
```

**Solution**: Set your API key:
```bash
export ANTHROPIC_API_KEY="your_key_here"
```

### Timeout Errors

If tasks consistently timeout, increase the timeout:
```bash
python3 benchmark_runner.py --task tasks/TASK-001.yaml --timeout 600
```

## Next Steps

- **US-002**: Implement claude-loop execution adapter
- **US-003**: Implement agent-zero execution adapter
- **US-004**: Create task-specific acceptance criteria validators
- **US-005**: Execute full benchmark suite (9 runs)
- **US-006**: Statistical analysis of results
- **US-007**: Failure analysis

## Contributing

When adding new tasks:

1. Create task definition in `tasks/TASK-XXX.yaml`
2. Ensure acceptance criteria are specific and testable
3. Include context (background, constraints)
4. Specify fileScope if applicable
5. Test task loading: `python3 -c "from benchmark_runner import load_task_definition; load_task_definition('tasks/TASK-XXX.yaml')"`

## License

Same as claude-loop parent project.
