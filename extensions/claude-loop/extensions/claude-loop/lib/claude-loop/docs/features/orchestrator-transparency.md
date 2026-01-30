# Orchestrator Transparency

**Status**: Implemented (US-ORG-005)  
**Version**: 1.0  
**Last Updated**: 2026-01-17

## Overview

The Transparency Layer provides 4 levels of explanation for orchestrator decisions, from silent (no notification) to full audit (complete decision log). This allows users to understand why certain agents/skills were chosen at the appropriate level of detail.

**Key Capabilities**:
- **4 Transparency Levels**: Silent, Brief, Detailed, Full Audit
- **Adaptive Notification**: Auto-selects appropriate level based on decision significance
- **Formatted Explanations**: User-friendly output for each level
- **Integration**: Used by Human-in-the-Loop for approval gates

## Transparency Levels

### Level 0: Silent
**When**: Obvious/routine decisions (e.g., code-reviewer for code review)  
**Output**: No notification  
**Example**: Selecting test-runner for running tests

### Level 1: Brief
**When**: Significant automatic decisions  
**Output**: One-line notification  
**Example**: `ℹ️  Using brainstorming skill (complexity: 7/10); Using security-auditor agent (security risk detected)`

### Level 2: Detailed
**When**: Essential decisions requiring approval  
**Output**: Full rationale with alternatives and confidence  
**Includes**:
- Summary of routing decisions
- Rationale for each component
- Alternatives considered
- Overall confidence score
- Recommendations

### Level 3: Full Audit
**When**: On demand via `--explain` flag  
**Output**: Complete decision log with all rules evaluated  
**Includes**:
- Situation diagnosis details
- All routing decisions with priorities
- All rules evaluated (matched and unmatched)
- Alternatives considered
- Detailed recommendations

## Usage

### Basic Usage

```python
from lib.orchestrator.transparency import TransparencyLayer, TransparencyLevel
from lib.orchestrator.diagnosis import SituationDiagnosis
from lib.orchestrator.decision_engine import DecisionEngine

# Initialize components
diagnoser = SituationDiagnosis()
engine = DecisionEngine()
transparency = TransparencyLayer()

# User request
user_request = "build authentication system with JWT"

# Diagnose and decide
diagnosis = diagnoser.diagnose(user_request)
decisions = engine.decide(diagnosis)

# Generate explanation (Brief level)
explanation = transparency.explain(
    user_request,
    diagnosis,
    decisions,
    level=TransparencyLevel.BRIEF
)

# Format and display
formatted = transparency.format_explanation(explanation)
print(formatted)
# Output: ℹ️  Using brainstorming skill (complexity: 7/10); Using security-auditor agent (security domain)
```

### Auto-Select Appropriate Level

```python
# Let transparency layer decide the appropriate level
level = transparency.should_notify(
    decisions,
    user_expertise_level="intermediate"  # or "beginner", "expert"
)

explanation = transparency.explain(
    user_request,
    diagnosis,
    decisions,
    level=level
)
```

### CLI Interface

```bash
# Brief explanation (default)
python3 lib/orchestrator/transparency.py "build auth system"

# Detailed explanation
python3 lib/orchestrator/transparency.py "build auth system" --level 2

# Full audit
python3 lib/orchestrator/transparency.py "build auth system" --level 3
```

## API Reference

### TransparencyLayer

```python
class TransparencyLayer:
    def explain(
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        level: TransparencyLevel = TransparencyLevel.BRIEF
    ) -> Explanation
    
    def should_notify(
        decisions: DecisionResult,
        user_expertise_level: str = "intermediate"
    ) -> TransparencyLevel
    
    def format_explanation(
        explanation: Explanation
    ) -> str
```

### TransparencyLevel Enum

```python
class TransparencyLevel(int, Enum):
    SILENT = 0      # No notification
    BRIEF = 1       # One-line
    DETAILED = 2    # Full rationale
    FULL_AUDIT = 3  # Complete log
```

## Integration with Human-in-the-Loop

The transparency layer is used by the Human-in-the-Loop system for approval gates:

```python
from lib.orchestrator.human_in_loop import ApprovalGate

gate = ApprovalGate()

# Create approval request (uses Detailed level internally)
approval_request = gate.request_approval(
    user_request,
    diagnosis,
    decisions
)

# User asks for more detail → Full Audit
full_explanation = gate.explain_before_approval(
    user_request,
    diagnosis,
    decisions
)
```

## Test Coverage

**Test Suite**: `tests/orchestrator/test_transparency.py` (15 tests, all passing)

**Coverage**:
- All 4 transparency levels
- Auto-selection logic
- Formatting for each level
- Expert user adjustments
- Multi-component explanations

## References

- **Human-in-the-Loop**: `docs/features/human-in-the-loop.md`
- **Decision Engine**: `docs/architecture/decision-engine.md`
- **PRD**: `prds/drafts/intelligent-orchestration-system/prd.json` (US-ORG-005)
