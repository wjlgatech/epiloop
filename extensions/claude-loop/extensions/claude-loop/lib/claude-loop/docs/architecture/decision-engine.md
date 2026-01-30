# Decision Engine Architecture

**Status**: Implemented (US-ORG-003)
**Version**: 1.0
**Last Updated**: 2026-01-17

## Overview

The Decision Engine is the core routing component of the intelligent orchestrator. It analyzes situation diagnosis results and routes requests to the appropriate agents, skills, and workflows based on configurable routing rules.

**Key Capabilities**:
- **Rule-based Routing**: Routes to components based on YAML-configured rules
- **Priority-based Execution**: Orders execution by priority (mandatory → risk-based → domain-based → sequential → supporting)
- **Timing Awareness**: Schedules components before/during/after implementation
- **Human-in-the-Loop**: Detects essential decisions requiring human approval
- **Performance**: <100ms decision time for typical requests

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Decision Engine                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Load Rules          config/orchestrator-rules.yaml          │
│     │                                                           │
│     ├─→ Skills Rules    (mandatory enforcement)                │
│     ├─→ Agent Rules     (risk-based, domain-based)             │
│     ├─→ Workflow Rules  (sequential execution)                 │
│     └─→ HITL Rules      (essential decisions)                  │
│                                                                 │
│  2. Apply Rules in Priority Order                              │
│     │                                                           │
│     ├─→ Mandatory Skills    (Priority 1)                       │
│     ├─→ Risk-based Agents   (Priority 2)                       │
│     ├─→ Domain-based Agents (Priority 3)                       │
│     └─→ Sequential Workflows (Priority 4)                      │
│                                                                 │
│  3. Deduplication & Ordering                                   │
│     │                                                           │
│     ├─→ Remove Duplicates (keep highest priority)              │
│     ├─→ Sort by Priority & Timing                              │
│     └─→ Generate Execution Order                               │
│                                                                 │
│  4. Human Approval Check                                       │
│     │                                                           │
│     ├─→ Destructive Operations?                                │
│     ├─→ Production Deployments?                                │
│     ├─→ Architectural Decisions?                               │
│     └─→ Budget Thresholds?                                     │
│                                                                 │
│  5. Return DecisionResult                                      │
│     │                                                           │
│     ├─→ List of Routing Decisions                             │
│     ├─→ Execution Order                                        │
│     ├─→ Total Confidence                                       │
│     └─→ Human Approval Required?                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Structures

#### RoutingDecision
```python
@dataclass
class RoutingDecision:
    component_type: str        # "skill", "agent", "workflow"
    component_name: str        # e.g., "brainstorming", "security-auditor"
    rationale: str             # Why this component was selected
    confidence: float          # 0.0-1.0
    priority: Priority         # MANDATORY, RISK_BASED, DOMAIN_BASED, SEQUENTIAL, SUPPORTING
    timing: Optional[str]      # "before_implementation", "after_implementation", None
    alternatives_considered: List[str]
    rule_applied: str          # e.g., "agents.security-auditor.when[1]"
```

#### DecisionResult
```python
@dataclass
class DecisionResult:
    decisions: List[RoutingDecision]      # All routing decisions
    total_confidence: float                # Average confidence
    execution_order: List[str]             # Ordered list of components
    human_approval_required: bool          # True if essential decision
    approval_reason: str                   # Why approval is needed
```

#### Priority Enum
```python
class Priority(int, Enum):
    MANDATORY = 1      # Skills that MUST be used
    RISK_BASED = 2     # Agents triggered by HIGH risk
    DOMAIN_BASED = 3   # Agents based on primary domain
    SEQUENTIAL = 4     # Workflows with timing constraints
    SUPPORTING = 5     # Lower priority support agents
```

## Routing Rules Format

Rules are defined in `config/orchestrator-rules.yaml` with the following structure:

### Skill Rules

```yaml
skills:
  brainstorming:
    when:
      - condition: "complexity >= 5"
        confidence: 0.95
      - condition: "keywords contains ['design', 'architect', 'refactor']"
        confidence: 0.90
    mandatory: true
    priority: 1
    rationale: "High complexity or design keywords detected"
    timing: null  # Run during implementation (default)
```

**Fields**:
- `when`: List of conditions (OR logic - any condition can trigger)
  - `condition`: Condition string (see Condition Syntax below)
  - `confidence`: Confidence score for this condition (0.0-1.0)
- `mandatory`: If true, assigned Priority.MANDATORY
- `priority`: Numeric priority for ordering (lower = earlier)
- `rationale`: Human-readable explanation
- `timing`: Optional timing constraint ("before_implementation", "after_implementation", or null)
- `note`: Optional note (if contains "TODO" and "not yet implemented", skill is skipped)

### Agent Rules

```yaml
agents:
  security-auditor:
    when:
      - condition: "primary_domain == 'security'"
        confidence: 1.0
      - condition: "risks contains 'security' with level HIGH"
        confidence: 0.95
      - condition: "secondary_domains contains 'security'"
        confidence: 0.85
    priority: 1
    rationale: "Security domain or HIGH security risk detected"
```

**Priority Assignment**:
- If matched condition contains `"risks contains"` and `"with level HIGH"` → Priority.RISK_BASED (2)
- Otherwise → Priority.DOMAIN_BASED (3)

### Workflow Rules

```yaml
workflows:
  two-stage-review:
    when:
      - condition: "operation_type in ['creation', 'modification']"
        confidence: 1.0
    enabled_by_default: true
    stages:
      - name: "spec-compliance"
        description: "Stage 1: Verify requirements met"
        tool: "lib/spec-compliance-reviewer.py"
      - name: "code-quality"
        description: "Stage 2: Code quality review"
        tool: "run_review_panel"
    priority: 5
    rationale: "All implementation work requires two-stage review"
```

**Priority Assignment**: All workflows get Priority.SEQUENTIAL (4)

### Human-in-the-Loop Rules

```yaml
human_in_loop:
  essential_decisions:
    - category: "destructive_operations"
      patterns:
        - "git push --force"
        - "rm -rf"
        - "drop database"
      approval_required: true
      transparency_level: "detailed"

    - category: "production_deployments"
      patterns:
        - "deploy to production"
        - "release to prod"
      approval_required: true

    - category: "architectural_decisions"
      patterns:
        - "multiple valid approaches"
        - "trade-offs between"
      approval_required: true

    - category: "budget_thresholds"
      conditions:
        - "estimated_cost > 10.00"  # USD
      approval_required: true

  routine_decisions:
    - "agent selection"
    - "skill invocation"
    - "code quality decisions"
```

## Condition Syntax

Conditions are string expressions evaluated against the `DiagnosisResult`. Supported syntax:

### Complexity Conditions
```yaml
"complexity >= 5"      # Complexity score threshold
"complexity < 3"       # Upper bound
```

### Operation Type Conditions
```yaml
"operation_type == 'creation'"                        # Exact match
"operation_type in ['creation', 'modification']"      # Multiple options
```

**Valid Operation Types**: `creation`, `modification`, `debugging`, `analysis`, `planning`

### Domain Conditions
```yaml
"primary_domain == 'security'"                        # Primary domain exact match
"domains contains 'security'"                         # Any domain (primary or secondary)
"secondary_domains contains 'testing'"                # Secondary domain only
```

**Valid Domains**: `frontend`, `backend`, `testing`, `infrastructure`, `security`, `documentation`, `planning`

### Risk Conditions
```yaml
"risks contains 'security'"                           # Any security risk
"risks contains 'security' with level HIGH"           # HIGH security risk only
"risks contains 'breaking_changes'"                   # Breaking changes risk
```

**Valid Risk Categories**: `security`, `breaking_changes`, `data_loss`
**Valid Risk Levels**: `HIGH`, `MEDIUM`, `LOW`

### Keywords Conditions
```yaml
"keywords contains 'test'"                            # Single keyword
"keywords contains ['test', 'coverage']"              # Multiple keywords (OR)
```

### Skill Mandatory Condition
```yaml
"test-driven-development skill is mandatory"          # Check if skill in capabilities_needed
```

## Execution Order Algorithm

Execution order is determined by:

1. **Timing Phase**: Components are grouped into three phases:
   - **Before Implementation**: Timing = "before_implementation"
   - **During Implementation**: Timing = null or "during"
   - **After Implementation**: Timing = "after_implementation"

2. **Priority Within Phase**: Within each phase, components are sorted by priority (lower enum value = higher priority):
   - Priority.MANDATORY (1) → First
   - Priority.RISK_BASED (2)
   - Priority.DOMAIN_BASED (3)
   - Priority.SEQUENTIAL (4)
   - Priority.SUPPORTING (5) → Last

3. **Final Order**: `[Before] + [During] + [After]`

**Example**:
```python
# Input decisions:
# - brainstorming (MANDATORY, timing=null)
# - tdd-enforcement (SEQUENTIAL, timing="before_implementation")
# - security-auditor (RISK_BASED, timing=null)
# - code-reviewer (DOMAIN_BASED, timing="after_implementation")

# Output execution_order:
[
    "workflow:tdd-enforcement",      # Before phase: SEQUENTIAL
    "skill:brainstorming",           # During phase: MANDATORY (priority 1)
    "agent:security-auditor",        # During phase: RISK_BASED (priority 2)
    "agent:code-reviewer"            # After phase: DOMAIN_BASED
]
```

## Deduplication Strategy

When multiple conditions trigger the same component:

1. **Group by Component**: Group all decisions by `(component_type, component_name)`
2. **Keep Highest Priority**: For each component, keep the decision with the highest priority (lowest enum value)
3. **Preserve Metadata**: The kept decision retains the rule_applied, rationale, and confidence from the highest-priority match

**Example**:
```python
# security-auditor triggered by two conditions:
# - Condition 0: "primary_domain == 'security'" (DOMAIN_BASED, priority=3)
# - Condition 1: "risks contains 'security' with level HIGH" (RISK_BASED, priority=2)

# Result: Keep the RISK_BASED version (priority 2 < 3)
RoutingDecision(
    component_name="security-auditor",
    priority=Priority.RISK_BASED,
    rule_applied="agents.security-auditor.when[1]"
)
```

## Human-in-the-Loop Detection

Human approval is required when any of the following conditions are met:

### Destructive Operations
Patterns: `["git push --force", "rm -rf", "drop database", "truncate table", "delete production data"]`

**Detection**: Check if any pattern appears in `diagnosis.keywords_detected`

### Production Deployments
Patterns: `["deploy to production", "release to prod", "production environment"]`

**Detection**: Check if any pattern appears in `diagnosis.keywords_detected`

### Architectural Decisions
Threshold: `complexity >= 7`

**Detection**: High complexity indicates architectural decisions requiring human review

### Budget Thresholds
Threshold: `estimated_cost > 10.00` (USD)

**Detection**: NOT YET IMPLEMENTED (requires cost estimation in diagnosis phase)

## API Reference

### DecisionEngine

```python
class DecisionEngine:
    def __init__(self, rules_file: str = None):
        """
        Initialize decision engine.

        Args:
            rules_file: Path to orchestrator-rules.yaml
                       Default: config/orchestrator-rules.yaml
        """

    def decide(self, diagnosis: DiagnosisResult) -> DecisionResult:
        """
        Make routing decisions based on diagnosis.

        Args:
            diagnosis: DiagnosisResult from situation diagnosis engine

        Returns:
            DecisionResult with routing decisions and execution order

        Performance: <100ms for typical requests
        """
```

### Usage Example

```python
from lib.orchestrator.diagnosis import SituationDiagnosis
from lib.orchestrator.decision_engine import DecisionEngine

# Step 1: Diagnose the situation
diagnoser = SituationDiagnosis()
diagnosis = diagnoser.diagnose("build authentication with JWT tokens")

# Step 2: Make routing decisions
engine = DecisionEngine()
result = engine.decide(diagnosis)

# Step 3: Process results
print(f"Total Confidence: {result.total_confidence:.2f}")
print(f"Human Approval Required: {result.human_approval_required}")

for decision in result.decisions:
    print(f"\n{decision.component_type.upper()}: {decision.component_name}")
    print(f"  Priority: {decision.priority.name}")
    print(f"  Rationale: {decision.rationale}")
    print(f"  Rule: {decision.rule_applied}")

print(f"\nExecution Order:")
for idx, component in enumerate(result.execution_order, 1):
    print(f"  {idx}. {component}")
```

## Performance Characteristics

| Metric | Target | Typical |
|--------|--------|---------|
| Decision Time | <100ms | 10-30ms |
| Memory Usage | <50MB | 10-20MB |
| Rule Evaluation | <50ms | 5-10ms |
| Total Decisions | 1-10 | 3-5 |

**Scalability**:
- Rules: 50+ skills/agents/workflows supported
- Conditions: 100+ condition evaluations per request
- Decisions: 10+ routing decisions without performance degradation

## Testing

### Test Coverage

**Test Suite**: `tests/orchestrator/test_decision_engine.py` (30 test cases)

**Coverage Areas**:
1. **Skill Routing** (Tests 1-2): Brainstorming triggered by complexity/keywords
2. **Agent Routing - Security** (Tests 3-4): Domain vs. HIGH risk priority
3. **Agent Routing - Code Review** (Tests 5-6): Creation/modification triggers
4. **Agent Routing - Testing** (Tests 7-10): Domain/keywords/operation triggers
5. **Agent Routing - Git** (Test 11): Keyword triggers
6. **Workflow Routing** (Tests 12-14): Creation/modification triggers, timing
7. **Execution Order** (Tests 15-16): Timing and priority ordering
8. **Deduplication** (Test 17): Priority-based deduplication
9. **Human-in-the-Loop** (Tests 18-21): Essential vs. routine decisions
10. **Metadata** (Tests 22-23): Confidence scoring, rule tracking
11. **Unimplemented Skills** (Tests 24-25): TODO skills skipped
12. **Multi-Domain** (Test 26): Secondary domain triggers
13. **Integration** (Tests 27-30): Complex scenarios, edge cases

**Running Tests**:
```bash
python3 tests/orchestrator/test_decision_engine.py
```

**Expected Output**:
```
============================================================
DECISION ENGINE TEST SUITE
============================================================

✅ Test 1: Brainstorming triggered by complexity
✅ Test 2: Brainstorming triggered by keywords
... (28 more tests)

============================================================
RESULTS: 30/30 tests passed
✅ All tests passed!
============================================================
```

## Integration Points

### Input: Situation Diagnosis Engine
```python
# diagnosis.py provides DiagnosisResult
from lib.orchestrator.diagnosis import DiagnosisResult, Domain, OperationType, Risk, RiskLevel

# Decision engine consumes this structure
diagnosis = DiagnosisResult(
    complexity=7,
    primary_domain=Domain.SECURITY,
    operation_type=OperationType.CREATION,
    risks=[Risk(category="security", level=RiskLevel.HIGH, ...)],
    keywords_detected=["authentication", "JWT"],
    capabilities_needed=[]
)
```

### Output: Orchestrator Integration
```python
# Orchestrator uses DecisionResult to:
# 1. Load agent/skill/workflow prompts
# 2. Execute components in order
# 3. Request human approval if needed
# 4. Log decisions for accountability

result = engine.decide(diagnosis)

for component_id in result.execution_order:
    comp_type, comp_name = component_id.split(":", 1)

    if comp_type == "skill":
        invoke_skill(comp_name)
    elif comp_type == "agent":
        load_agent_prompt(comp_name)
    elif comp_type == "workflow":
        execute_workflow(comp_name)
```

## Configuration Management

### Adding New Rules

1. **Edit** `config/orchestrator-rules.yaml`
2. **Add Rule** under appropriate section (skills/agents/workflows)
3. **Test** with `python3 lib/orchestrator/decision_engine.py '<diagnosis_json>'`
4. **Validate** with test suite

**Example - Add New Agent**:
```yaml
agents:
  performance-profiler:
    when:
      - condition: "keywords contains ['performance', 'slow', 'bottleneck']"
        confidence: 0.85
      - condition: "primary_domain == 'backend'"
        confidence: 0.80
    priority: 2
    rationale: "Performance issues detected"
```

### Tuning Confidence Scores

Confidence scores (0.0-1.0) affect `total_confidence` but not routing decisions.

**Guidelines**:
- `1.0`: Unambiguous triggers (exact domain match, HIGH risk)
- `0.9-0.95`: Strong indicators (keyword matches, operation type)
- `0.8-0.85`: Moderate confidence (secondary domains, multiple conditions)
- `0.7-0.75`: Lower confidence (heuristics, weak signals)

### Disabling Components

**Temporary Disable**: Add `enabled: false` to rule
```yaml
agents:
  security-auditor:
    enabled: false  # Temporarily disabled
    when: ...
```

**Permanent Disable (TODO)**: Add note with "TODO" and "not yet implemented"
```yaml
skills:
  systematic-debugging:
    note: "TODO: Skill not yet implemented, enforcement disabled"
    when: ...
```

## Troubleshooting

### Component Not Triggering

**Diagnosis**:
```bash
# Run with debug output
python3 lib/orchestrator/diagnosis.py "your request" --json | \
python3 lib/orchestrator/decision_engine.py -
```

**Check**:
1. Is condition syntax correct?
2. Does diagnosis meet condition criteria?
3. Is component marked as TODO?
4. Is `enabled: false` in rule?

### Wrong Priority Assigned

**Issue**: Component gets wrong priority (e.g., RISK_BASED instead of DOMAIN_BASED)

**Cause**: Multiple conditions matched, highest priority kept

**Solution**: Check which condition was matched in `rule_applied` field

### Human Approval Not Triggering

**Check**:
1. Are keywords in `diagnosis.keywords_detected`?
2. Is complexity >= 7 for architectural decisions?
3. Are patterns in `human_in_loop.essential_decisions` correct?

## Future Enhancements

### Planned (US-ORG-004 through US-ORG-011)
- **Accountability Layer**: Decision logging and learning
- **Transparency Layer**: Explanations with confidence breakdown
- **Benchmark Framework**: Regression detection and quality metrics
- **Integration**: Full claude-loop.sh integration
- **Tuning**: Confidence threshold calibration

### Under Consideration
- **Machine Learning**: Learn from decision outcomes to improve rules
- **Cost Estimation**: Budget threshold enforcement
- **Parallel Execution**: Concurrent agent/skill invocation
- **Dynamic Rules**: Runtime rule generation based on project patterns

## References

- **Situation Diagnosis Engine**: `docs/architecture/situation-diagnosis.md`
- **Accountability Layer**: `docs/architecture/accountability-layer.md` (TODO)
- **Transparency Layer**: `docs/architecture/transparency-layer.md` (TODO)
- **Orchestrator Overview**: `docs/analysis/orchestration-audit-2026-01-16.md`
- **PRD**: `prds/drafts/intelligent-orchestration-system/prd.json`
