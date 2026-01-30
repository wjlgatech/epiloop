# Claude-Loop Self-Improvement Strategy

## Research Date: 2026-01-11

## Executive Summary

This document captures the strategic analysis of making claude-loop self-improving - capable of detecting its own capability gaps, generalizing them, and autonomously generating improvement plans without blocking active work.

---

## Problem Statement

When claude-loop encounters tasks it cannot complete satisfactorily, the system currently lacks:

1. **Gap Detection** — Mechanisms to recognize when output quality falls below acceptable thresholds
2. **Causal Attribution** — Deep analysis of *why* the gap exists, traced to root capabilities
3. **Generalization** — Abstraction from specific failure instances to broader capability categories
4. **Autonomous Remediation** — Background generation of PRDs for capability improvements
5. **Human-Free Initiation** — The loop operates without requiring human intervention to trigger

---

## Case Study: Unity GUI Automation Gap

### What Happened

```
1. TASK: Set up Quest 3 passthrough in Unity
2. ATTEMPT: AppleScript to click "+" button in Building Blocks panel
3. FAILURE: "Element not found" error
4. HUMAN OBSERVATION: AppleScript works for menus but not custom UI panels
5. HUMAN ATTRIBUTION: Gap is vision-based interaction with non-native UI
6. HUMAN GENERALIZATION: Applies to any app with custom UI (Electron, Qt, Unity)
7. HUMAN PRD: Created 10 stories for vision-based GUI automation
8. CLAUDE-LOOP EXECUTION: Implemented all 10 stories successfully
```

### Key Insight

Steps 4-7 were human-driven. The automation gap was in **detecting and attributing** the failure, not in **implementing** the fix.

---

## Five Self-Improvement Strategies Analyzed

### Strategy A: Post-Hoc Failure Analysis (Reactive)

```
Task Complete → Evaluate → [If gap] → Analyze → PRD → Queue
```

| Pros | Cons |
|------|------|
| Simple implementation | Only learns from failures |
| Low overhead on success | Latency before improvement |
| Clear trigger conditions | May fail repeatedly before fix |

**Best for:** Early-stage, when you can tolerate repeated failures.

### Strategy B: Predictive Gap Detection (Proactive)

```
Task Received → Predict Difficulty → [If uncertain] → Flag + Attempt → Learn
```

| Pros | Cons |
|------|------|
| Catches gaps before full failure | Requires good uncertainty estimation |
| Builds calibration | May be overly conservative |
| Can request help proactively | Computational overhead |

**Best for:** High failure cost, human-in-the-loop available.

### Strategy C: Continuous Skill Inventory (Systematic)

```
Maintain skill taxonomy → Map tasks to skills → Gap = required - possessed
```

| Pros | Cons |
|------|------|
| Explicit, auditable | Requires upfront taxonomy |
| Systematic prioritization | Can't enumerate unknown unknowns |
| Generalizes naturally | Maintenance burden |

**Best for:** Well-defined domains with enumerable skill sets.

### Strategy D: Counterfactual Simulation (Deep Analysis)

```
Actual:       A → B → C → [FAIL]
Counterfactual: A → B → D → E → [SUCCESS]
Gap:          Capability to choose D over C
```

| Pros | Cons |
|------|------|
| Precise causal attribution | Computationally expensive |
| Identifies minimal interventions | Requires simulation capability |
| Discovers non-obvious gaps | May identify unfixable gaps |

**Best for:** High-value failures where precise root cause matters.

### Strategy E: Ensemble Disagreement (Redundant Execution)

```
Approach 1: Result X
Approach 2: Result Y
Approach 3: Result X
→ Disagreement signals uncertainty/gap in Approach 2
```

| Pros | Cons |
|------|------|
| No ground truth needed | 2-3x computational cost |
| Works for subjective tasks | Requires different approaches |
| Built-in redundancy | Doesn't explain why |

**Best for:** When ground truth is unavailable or subjective.

---

## Recommended Hybrid Architecture

### Phase Mapping

| Phase | Strategy | Rationale |
|-------|----------|-----------|
| Pre-execution | B (Predictive) | Flag uncertainty early |
| Execution | C (Skill Inventory) | Track which skills used |
| Post-execution | A (Reactive) + D (Counterfactual) | Standard + deep analysis |
| Background | Continuous PRD generation | Non-blocking improvement |

### Simplified 3-Phase Implementation

Rather than the full 6-module architecture, implement pragmatically:

```
Phase 1: Structured Failure Logging
    ↓ (collect data for 2-4 weeks)
Phase 2: Pattern Recognition (semi-automated)
    ↓ (human-reviewed clusters)
Phase 3: PRD Generation (automated, human-approved)
```

---

## The Attribution Problem

**This is THE hard problem.** The proposal treats attribution as one of several challenges, but it's the gating factor.

```
Failure → ?????? → Root Cause → Capability Gap → PRD
              ↑
         90% of difficulty lives here
```

An agent cannot reliably reason about its own limitations because those limitations affect its reasoning. This is the blind spot problem.

### Failure Classification Taxonomy

Before building infrastructure, validate that claude-loop can classify:

| Category | Definition | Fixable? |
|----------|------------|----------|
| SUCCESS | Completed as expected | N/A |
| TASK_FAILURE | Task was impossible/ill-defined | No |
| CAPABILITY_GAP | Missing capability prevented success | Yes |
| BAD_LUCK | Edge case / transient failure | Usually no |

**Validation requirement:** >80% accuracy on 20 labeled historical executions before proceeding.

---

## Critical Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Misattribution** | High | Require multiple instances before PRD |
| **Overfitting** | High | Generalization module + held-out tests |
| **Runaway modification** | Medium | Regression tests, rollback mechanism |
| **Priority inversion** | Medium | Frequency-weighted scoring |
| **Infinite loop** | Low | Rate limiting, improvement budget |

---

## Key Insight

The hard part isn't executing improvements. We proved this with Unity automation - 10 stories, all implemented successfully.

**The hard part is knowing which improvements matter.**

Once you can reliably identify capability gaps (with human validation), the improvement execution is straightforward.

---

## Decision: Pragmatic Over Autonomous

| Aspect | Fully Autonomous | Human-in-the-Loop (Chosen) |
|--------|-----------------|---------------------------|
| Complexity | High | Low |
| Safety | Risky | Safe |
| Time to value | 5+ weeks | 2 weeks |
| Attribution accuracy | Assumed | Validated |
| Scalability | Designed for scale | Designed for learning |

**Rationale:** Start with human-in-the-loop, graduate to autonomous as confidence increases.

---

## Implementation Roadmap

1. **Week 1-2:** Structured failure logging
2. **Week 3:** Failure pattern analyzer
3. **Week 4:** PRD generator (human-approved)
4. **Week 5:** Review interface + first improvement cycle
5. **Future:** Gradually reduce human involvement as accuracy improves

---

## References

- Gap Analysis: `/docs/GAP-ANALYSIS-Unity-Editor-Automation.md`
- Vision GUI PRD: `/prd-vision-gui-automation.json`
- This strategy: `/docs/SELF-IMPROVEMENT-STRATEGY.md`

---

*Document created: 2026-01-11*
*Author: Claude Code Analysis + Human Discussion*
