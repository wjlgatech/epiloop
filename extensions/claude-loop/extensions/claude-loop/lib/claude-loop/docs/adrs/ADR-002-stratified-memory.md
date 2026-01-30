# Scale Architecture Decision Record

## Problem Statement

**Date**: 2026-01-11
**Context**: Planning for claude-loop to scale to 1000 users × 5 projects/week = 5,000 projects/week

**Core Question**: How do we handle self-improvement at scale without bloating claude-loop? How do we keep the core lean while accumulating experience?

## Initial Proposal (v1)

### Stratified Memory Architecture

```
L0: Core (Immutable)
    - claude-loop.sh, lib/*.sh
    - NEVER modified by self-improvement
    - Changes require human PR review

L1: Domain Adapters
    - agents/*.md (bundled specialists)
    - Stable patterns, rarely change
    - Promoted from L2 after 100+ successful uses

L2: Experience Store (RAG, not compiled)
    - Vector DB of problem-solution pairs
    - Retrieved at runtime, not baked into code
    - Ephemeral: entries decay if not useful

L3: Improvement Queue
    - Pending proposals awaiting promotion
    - Gated by success metrics
```

### Key Principle: Memory ≠ Code

Experience is stored as embeddings, retrieved via RAG at runtime - NOT compiled into the codebase. This prevents bloat while enabling learning.

### Proposed Components

1. **Experience Store** - Vector DB (ChromaDB) for problem-solution pairs
2. **Federated Aggregation** - Optional telemetry to share learnings across users
3. **Natural Selection** - Improvements must prove value before promotion
4. **Extension System** - Domain adapters as plugins

## Critical Feedback

The initial proposal received detailed critique identifying 8 fundamental gaps:

### Gap 1: Aggregation Assumes Homogeneity

> "Same symptom in different domains (Unity vs Isaac Sim vs Web) are different problems"

**Problem**: Treating "build failed" the same across Unity game dev, Isaac Sim robotics, and web frontend would produce useless generalized solutions.

**Example**: A "dependency resolution" fix for npm is completely different from one for Unity Package Manager.

### Gap 2: Cold Start Problem

> "Experience store is useless until it has critical mass"

**Problem**: New users get no benefit. What bootstraps the system?

**Questions**:
- How many experiences before retrieval becomes useful?
- What's the quality bar for initial entries?

### Gap 3: Privacy/IP Concerns

> "Federated model has showstopper privacy issues"

**Problem**: Users won't share experiences if they contain:
- Proprietary code patterns
- Internal tool names
- Business logic details

**Reality**: Most enterprises will reject any telemetry.

### Gap 4: Promotion Criteria Insufficient

> "Missing: maintenance cost, dependency risk, reversibility"

**Problem**: Success rate alone doesn't capture:
- Does this improvement add complexity?
- Does it introduce new dependencies?
- Can it be safely rolled back?

### Gap 5: Compression Underspecified

> "Human-assisted clustering, not auto-compression"

**Problem**: Automatic pattern compression could:
- Merge semantically different problems
- Lose important context
- Create false generalizations

### Gap 6: No Conflict Handling

> "What happens when two improvements contradict?"

**Problem**: Improvement A says "always use TypeScript strict mode" while Improvement B says "disable strict for legacy codebases". No system to detect or resolve.

### Gap 7: Lagging Metrics

> "Success rate is lagging. Need leading indicators"

**Problem**: By the time success rate drops, damage is done.

**Better signals**:
- Proposal rate changes (are we generating more/fewer?)
- Cluster concentration (are we over-indexing on one area?)
- Retrieval miss rate (are we missing relevant experiences?)

### Gap 8: Bootstrap Problem

> "Who validates the validators?"

**Problem**: The calibration system itself needs calibration.

**Questions**:
- How do we know the human reviewers are making good decisions?
- What prevents gaming the metrics?
- How do we handle reviewer disagreement?

## Revised Architecture (v2)

### Design Principles

1. **FULLY_LOCAL by default** - No telemetry without explicit opt-in
2. **Human-gated improvements** - NO automatic code generation
3. **Domain-contextualized** - Same symptom in different domains = different problems
4. **Earned autonomy** - 95% alignment over 6 months before any automation
5. **Leading indicators** - Detect problems before they manifest

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    L0: IMMUTABLE CORE                       │
│  claude-loop.sh, lib/*.sh - NEVER auto-modified            │
│  Changes require human PR review                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  L1: DOMAIN ADAPTERS                        │
│  agents/*.md - Domain-specific specialists                  │
│  Promoted from L2 after human review + 100 successes       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            L2: EXPERIENCE STORE (RAG Layer)                 │
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ web/*      │ │ unity/*     │ │ physical/* │          │
│  │ frontend   │ │ game        │ │ robotics   │          │
│  │ backend    │ │ xr          │ │ datacenter │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                             │
│  - Domain-prefixed embeddings: [unity:csharp] problem      │
│  - Feedback loop: helpful_rate tracking                    │
│  - Decay: unhelpful experiences lose weight                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              L3: HUMAN-GATED IMPROVEMENT QUEUE              │
│                                                             │
│  Proposal → Conflict Check → Human Review → Staging → L1   │
│                                                             │
│  Promotion Criteria:                                        │
│  - success_rate >= 0.85                                    │
│  - usage_count >= 100                                      │
│  - maintenance_cost_estimate <= LOW                        │
│  - dependency_risk <= MINIMAL                              │
│  - reversibility = true                                    │
│  - human_approval = REQUIRED                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Innovations in v2

#### 1. Domain-Contextualized Experience Store

```python
class DomainContext:
    project_type: str      # unity_xr, isaac_sim, web_backend
    language: str          # csharp, python, typescript
    frameworks: List[str]  # specific frameworks used
    tools_used: List[str]  # build tools, etc.
```

Embeddings are prefixed: `[unity:csharp:xr] NullReferenceException in Update loop`

Search filters by domain, preventing cross-contamination.

#### 2. Retrieval Feedback Loop

Every retrieved experience tracks:
- Was it marked helpful? (explicit feedback)
- Was the task completed after retrieval? (implicit signal)
- How long did the user spend? (engagement proxy)

Unhelpful experiences decay. Helpful ones strengthen.

#### 3. Human-Gated Everything

```
Improvement Pipeline:
1. Pattern detected → Proposal created (automated)
2. Conflict check → Flag contradictions (automated)
3. Human review → Approve/reject/modify (REQUIRED)
4. Staging test → Run on sample projects (automated)
5. Promotion → Move to L1 (requires human sign-off)
```

NO automatic code changes. Ever.

#### 4. Conflict Detection System

Before any promotion:
```python
def check_conflicts(proposal):
    # Check preconditions overlap
    for existing in get_existing_improvements():
        if overlapping_scope(proposal, existing):
            if contradictory_recommendations(proposal, existing):
                flag_for_human_resolution()
```

#### 5. Leading Indicators

| Metric | What It Detects | Threshold |
|--------|-----------------|-----------|
| proposal_rate_change | System generating too many/few proposals | >20% week-over-week |
| cluster_concentration | Over-indexing on one problem area | >40% in single cluster |
| retrieval_miss_rate | Experience store not covering user needs | >30% searches with no results |
| helpful_rate_trend | Quality degradation | <70% or declining |

#### 6. Calibration Tracking

Before ANY automation is considered:
```python
class CalibrationStatus:
    human_decisions: int           # Total human reviews
    system_would_agree: int        # Cases where system would match human
    alignment_rate: float          # system_would_agree / human_decisions
    calibration_period_months: int # How long we've been tracking

    def is_calibrated(self) -> bool:
        return (
            self.alignment_rate >= 0.95 and
            self.calibration_period_months >= 6 and
            self.human_decisions >= 500
        )
```

System must demonstrate 95% alignment with human decisions over 6 months before ANY autonomous action is considered.

### Privacy-First Design

```python
class PrivacyConfig:
    TELEMETRY_MODE = "FULLY_LOCAL"  # Default, no data leaves machine

    # Even with opt-in:
    NEVER_SHARE = [
        "source_code",
        "file_paths",
        "environment_variables",
        "api_keys",
        "internal_tool_names"
    ]

    # Can share (with consent):
    MAY_SHARE = [
        "anonymized_problem_category",
        "success/failure_binary",
        "domain_type"
    ]
```

## Implementation Stories

The v2 architecture is implemented across 16 user stories in `prd-stratified-memory-v2.json`:

| ID | Title | Purpose |
|----|-------|---------|
| SCALE-001 | Domain-Contextualized Experience Store | Domain-aware storage with partitioned collections |
| SCALE-002 | Experience Retrieval with Feedback Loop | Track helpful_rate, decay unhelpful |
| SCALE-003 | Automatic Experience Recording | Domain detection, deduplication |
| SCALE-004 | Privacy-First Local-Only Architecture | No telemetry by default |
| SCALE-005 | Domain Adapter Extension System | Plugin architecture for domains |
| SCALE-006 | Physical AI Domain Adapter | robotics, datacenter, warehouse |
| SCALE-007 | Human-Gated Improvement Queue | All promotions require human approval |
| SCALE-008 | Promotion Criteria with Lifecycle Cost | maintenance_cost, dependency_risk |
| SCALE-009 | Conflict Detection System | Detect contradictory improvements |
| SCALE-010 | Human-Assisted Pattern Clustering | No auto-compression |
| SCALE-011 | Leading Indicator Metrics | proposal_rate, cluster_concentration |
| SCALE-012 | Calibration Tracking System | 95% alignment over 6 months |
| SCALE-013 | Core Protection with Immutability Rules | L0 never auto-modified |
| SCALE-014 | Experience-Augmented Prompts | RAG integration with domain context |
| SCALE-015 | Team Experience Sharing (Local Only) | Opt-in local network sharing |
| SCALE-016 | Comprehensive Scale Architecture Tests | Verify all constraints |

## Key Decisions

### Decision 1: Memory Over Code

**Choice**: Experience stored in vector DB, retrieved at runtime via RAG
**Alternative Rejected**: Compiling learnings into code/prompts
**Rationale**: Prevents unbounded growth, allows decay, maintains core stability

### Decision 2: Human Gates Everywhere

**Choice**: All improvements require human approval
**Alternative Rejected**: Automatic promotion based on metrics
**Rationale**: Trust must be earned; 6-month calibration before any automation

### Decision 3: Domain Partitioning

**Choice**: Separate experience collections per domain
**Alternative Rejected**: Single unified experience store
**Rationale**: Prevents cross-contamination; Unity fixes shouldn't pollute web solutions

### Decision 4: Local-First Privacy

**Choice**: FULLY_LOCAL default, no telemetry
**Alternative Rejected**: Opt-out federated learning
**Rationale**: Enterprise adoption requires zero data leakage; can't build trust otherwise

### Decision 5: Leading Over Lagging Metrics

**Choice**: Monitor proposal_rate, cluster_concentration, retrieval_miss_rate
**Alternative Rejected**: Only track success_rate
**Rationale**: Detect degradation before it affects users

## Success Criteria

The scale architecture succeeds if:

1. **Core remains stable**: L0 files unchanged by automation for 1 year
2. **Experience value**: >70% helpful_rate on retrievals after 3 months
3. **No bloat**: Total experience store <500MB per domain after 1 year
4. **Human trust**: Calibration tracking shows >95% alignment
5. **Zero privacy incidents**: No accidental data sharing

## References

- `prd-stratified-memory-v2.json` - Implementation stories
- `lib/experience-store.py` - Domain-aware storage implementation
- `lib/domain-detector.py` - Project domain detection
- `lib/experience-recorder.py` - Automatic experience recording

---

*This document captures the architectural discussion and decisions made for scaling claude-loop's self-improvement capabilities while preventing bloat and maintaining human oversight.*
