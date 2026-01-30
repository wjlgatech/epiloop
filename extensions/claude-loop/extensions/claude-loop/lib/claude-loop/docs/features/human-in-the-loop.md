# Human-in-the-Loop Approval Gates

**Status**: Implemented (US-ORG-006)  
**Version**: 1.0  
**Last Updated**: 2026-01-17

## Overview

The Human-in-the-Loop system manages approval gates for essential decisions while automating routine decisions. It logs user overrides and learns from patterns to improve future recommendations.

**Key Capabilities**:
- **Decision Classification**: Automatic categorization as essential vs routine
- **Approval Gates**: Request human approval for essential decisions only
- **Override Logging**: Track when users reject recommendations
- **Learning Algorithm**: Adjust confidence based on override patterns

## Decision Categories

### Essential Decisions (Require Approval)

1. **Destructive Operations**
   - `git push --force`, `git reset --hard`
   - `rm -rf`, `drop database`, `truncate table`
   - `delete production data`

2. **Production Deployments**
   - `deploy to production`, `release to prod`
   - `production environment`

3. **Architectural Decisions**
   - High complexity (complexity >= 7)
   - Multiple valid approaches
   - Significant system changes

4. **Budget Thresholds**
   - Estimated cost > $10 USD (future enhancement)

5. **Complex Situations**
   - Multiple high-priority agents (>= 3 agents with priority <= 2)

### Routine Decisions (Automatic Approval)

- Agent selection for standard operations
- Skill invocation
- Code quality decisions
- Test execution
- File operations (read/write/edit)
- Low-medium complexity operations (complexity < 7)

## Usage

### Basic Classification

```python
from lib.orchestrator.human_in_loop import ApprovalGate, DecisionCategory

gate = ApprovalGate()

# Classify a decision
category, reason = gate.classify_decision(diagnosis, decisions)

if category == DecisionCategory.ESSENTIAL:
    print(f"⚠️  Approval required: {reason}")
else:
    print(f"✓ Automatic execution: {reason}")
```

### Request Approval

```python
# Create approval request
approval_request = gate.request_approval(
    user_request="deploy to production",
    diagnosis=diagnosis,
    decisions=decisions
)

# Show explanation to user (Detailed level)
formatted = gate.transparency.format_explanation(
    approval_request.explanation
)
print(formatted)

# Process user response
response = gate.process_approval(
    approval_request,
    ApprovalAction.APPROVE  # or REJECT, EXPLAIN
)
```

### Interactive Approval Flow

```python
# 1. Request approval
approval_request = gate.request_approval(
    user_request,
    diagnosis,
    decisions
)

# 2. Show explanation
print(gate.transparency.format_explanation(approval_request.explanation))

# 3. Get user input
user_choice = input("Approve? [Y/n/explain]: ").lower()

if user_choice == "explain":
    # Show full audit
    full_explanation = gate.explain_before_approval(
        user_request,
        diagnosis,
        decisions
    )
    print(gate.transparency.format_explanation(full_explanation))
    user_choice = input("Approve? [Y/n]: ").lower()

# 4. Process approval
if user_choice == "y" or user_choice == "":
    response = gate.process_approval(
        approval_request,
        ApprovalAction.APPROVE
    )
    print("✓ Approved - proceeding with execution")
else:
    notes = input("Reason for rejection: ")
    response = gate.process_approval(
        approval_request,
        ApprovalAction.REJECT,
        notes=notes
    )
    print("✗ Rejected - aborting execution")
```

### Learn from User Overrides

```python
# Get statistics
stats = gate.get_override_statistics()
print(f"Total Overrides: {stats['total_overrides']}")
print(f"Most Rejected Components:")
for item in stats['most_rejected_components']:
    print(f"  {item['component']}: {item['count']}")

# Get learning recommendations
adjustments = gate.learn_from_overrides()
for component, multiplier in adjustments.items():
    if multiplier < 0.9:
        print(f"↓ Consider decreasing confidence for {component}: {multiplier:.2f}x")
```

### CLI Interface

```bash
# Classify a decision
python3 lib/orchestrator/human_in_loop.py classify "deploy to production"

# Simulate approval workflow
python3 lib/orchestrator/human_in_loop.py approve "deploy to production"

# Get override statistics
python3 lib/orchestrator/human_in_loop.py stats

# Get learning recommendations
python3 lib/orchestrator/human_in_loop.py learn
```

## API Reference

### ApprovalGate

```python
class ApprovalGate:
    def classify_decision(
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Tuple[DecisionCategory, str]
    
    def request_approval(
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult,
        request_id: str = None
    ) -> ApprovalRequest
    
    def process_approval(
        approval_request: ApprovalRequest,
        action: ApprovalAction,
        notes: Optional[str] = None
    ) -> ApprovalResponse
    
    def explain_before_approval(
        user_request: str,
        diagnosis: DiagnosisResult,
        decisions: DecisionResult
    ) -> Explanation
    
    def get_override_statistics() -> Dict
    
    def learn_from_overrides() -> Dict[str, float]
```

### Data Structures

```python
class DecisionCategory(str, Enum):
    ESSENTIAL = "essential"  # Requires approval
    ROUTINE = "routine"      # Automatic

class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EXPLAIN = "explain"  # Request full audit
    
@dataclass
class ApprovalRequest:
    request_id: str
    category: DecisionCategory
    reason: str
    decisions: DecisionResult
    explanation: Explanation  # Detailed level
    timestamp: str
```

## Override Logging

User rejections are logged to `.claude-loop/orchestrator-overrides.jsonl`:

```json
{
  "request_id": "a1b2c3d4",
  "timestamp": "2026-01-17T10:30:00Z",
  "user_request": "Routing to 3 components...",
  "rejected_components": ["agent:security-auditor", "workflow:tdd-enforcement"],
  "reason": "Not needed for this simple change",
  "alternative_taken": null
}
```

## Learning Algorithm

### How It Works

1. **Count Rejections**: Track how often each component is rejected
2. **Calculate Rejection Rate**: `rejections / total_recommendations`
3. **Suggest Adjustments**:
   - High rejection rate (>30%) → 0.7x multiplier (decrease confidence)
   - Medium rejection rate (15-30%) → 0.85x multiplier
   - Low rejection rate (<15%) → 0.95x multiplier

### Applying Adjustments

```python
adjustments = gate.learn_from_overrides()

for component, multiplier in adjustments.items():
    if multiplier < 0.9:
        print(f"Component {component} frequently rejected")
        print(f"Consider updating confidence in orchestrator-rules.yaml")
        print(f"Multiply current confidence by {multiplier:.2f}")
```

## Integration Flow

```
User Request
     ↓
Diagnosis Engine → Decision Engine
     ↓
ApprovalGate.classify_decision()
     ↓
┌────────────────────────────────┐
│   Essential?                   │
├────────────────────────────────┤
│ YES → request_approval()       │
│       show Detailed explanation│
│       get user input           │
│       process_approval()       │
│       if rejected → log override│
│                                │
│ NO  → execute automatically    │
│       (silent or brief notify) │
└────────────────────────────────┘
```

## Test Coverage

**Test Suite**: `tests/orchestrator/test_human_in_loop.py` (15 tests, all passing)

**Coverage**:
- Essential vs routine classification
- All essential decision categories
- Approval request creation
- Approve/reject/explain actions
- Override logging
- Statistics and learning

## References

- **Transparency Layer**: `docs/features/orchestrator-transparency.md`
- **Decision Engine**: `docs/architecture/decision-engine.md`
- **Accountability Layer**: `docs/architecture/accountability.md`
- **PRD**: `prds/drafts/intelligent-orchestration-system/prd.json` (US-ORG-006)
