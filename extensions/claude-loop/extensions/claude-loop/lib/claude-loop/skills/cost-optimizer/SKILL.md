# /cost-optimizer - Analyze Story Complexity and Recommend Models

Analyzes PRD stories and recommends optimal Claude models for cost-performance balance.

## Usage

```
/cost-optimizer
/cost-optimizer --skill-arg prd.json
./claude-loop.sh --skill cost-optimizer --skill-arg custom-prd.json
```

## What This Skill Does

Analyzes user stories and recommends models (Haiku/Sonnet/Opus):
1. **Complexity analysis**: Scores stories based on multiple factors
2. **Model recommendation**: Suggests optimal model for each story
3. **Cost estimation**: Estimates token usage and cost
4. **Savings calculation**: Shows potential savings vs always-Opus
5. **PRD updates**: Can update suggestedModel fields in PRD

## Complexity Factors

- File scope count (25%)
- Acceptance criteria count (25%)
- Keyword analysis (30%): security, architecture → complex; config, docs → simple
- Description length (10%)
- Dependencies count (10%)

## Model Recommendations

- **Haiku** (simple): Config changes, docs, simple scripts
- **Sonnet** (medium): Standard features, tests, refactoring
- **Opus** (complex): Security, architecture, complex algorithms

## Example Output

```
Cost Optimizer v1.0
===================

PRD: prd-phase2-foundations.json
Stories: 10

Story Analysis:
  US-201 [medium, sonnet]: Skills Architecture Core
    Complexity: 55/100
    Est. cost: $0.15

  US-202 [complex, opus]: Priority Skills Implementation
    Complexity: 85/100
    Est. cost: $0.45

Summary:
  Total estimated cost: $2.50
  Savings vs all-Opus: $1.20 (48%)
```

## Exit Codes

- `0` - Analysis completed successfully
- `1` - Error analyzing PRD
- `2` - Invalid arguments

## Script Implementation

Implemented in Python using the model-selector algorithm from lib/.
