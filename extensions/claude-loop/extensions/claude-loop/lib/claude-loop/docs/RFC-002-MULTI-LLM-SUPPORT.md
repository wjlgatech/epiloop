# RFC-002: Multi-LLM Support for claude-loop

**Status**: Draft
**Author**: Claude + Human collaboration
**Date**: 2026-01-12

## Executive Summary

Extend claude-loop to support multiple LLM providers (Google Gemini, OpenAI GPT, Alibaba Qwen, DeepSeek, GLM) while maintaining Claude Opus 4.5 as the default. This enables cost optimization, capability matching, and provider redundancy.

## Problem Statement

Currently, claude-loop is tightly coupled to Claude Code CLI. Users want:
1. **Cost optimization** — Use cheaper models for simpler tasks
2. **Capability matching** — Use vision models (VLMs) for image-heavy tasks
3. **Provider diversity** — Avoid single-vendor lock-in
4. **Benchmarking** — Compare model performance on their codebase

## Critical Constraints

### What Claude Code CLI Provides (That Others Don't)

| Capability | Claude Code | Other LLM APIs |
|------------|:-----------:|:--------------:|
| File system access | ✅ Native | ❌ Need agent framework |
| Bash execution | ✅ Native | ❌ Need agent framework |
| Git operations | ✅ Native | ❌ Need agent framework |
| Tool use | ✅ Native | ⚠️ Varies by provider |
| Streaming | ✅ | ✅ Most support |
| Vision (VLM) | ✅ | ⚠️ Some support |
| Long context | ✅ 200k | ⚠️ Varies (8k-2M) |

**Key insight**: To use other LLMs, we need to either:
1. Build our own agent runtime (significant work)
2. Use an existing agent framework (LangChain, AutoGen, CrewAI)
3. Use LLMs only for specific sub-tasks, not full story implementation

## Architectural Options

### Option A: Full Provider Abstraction

```
┌─────────────────────────────────────────────────────────────┐
│                    OPTION A: Full Abstraction                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   claude-loop.sh                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────┐                                           │
│   │ LLM Router  │ ◀── provider config                       │
│   └──────┬──────┘                                           │
│          │                                                   │
│    ┌─────┴─────┬─────────┬──────────┬──────────┐           │
│    ▼           ▼         ▼          ▼          ▼           │
│ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐         │
│ │Claude│  │Gemini│  │ GPT  │  │ Qwen │  │DeepSk│         │
│ │Code  │  │Agent │  │Agent │  │Agent │  │Agent │         │
│ └──────┘  └──────┘  └──────┘  └──────┘  └──────┘         │
│                                                              │
│   Each agent needs: file I/O, bash, git, tool use           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- Full flexibility to use any LLM for any task
- True provider independence

**Cons:**
- Massive engineering effort (build 5+ agent runtimes)
- Each provider's tool use is different
- Quality varies wildly between providers
- Maintenance nightmare

**Effort**: 6-12 months, 50k+ lines of code
**Recommendation**: ❌ Not recommended (too complex)

---

### Option B: Hybrid — Claude Orchestrator + Specialized Workers

```
┌─────────────────────────────────────────────────────────────┐
│                    OPTION B: Hybrid Architecture             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   claude-loop.sh                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────────────────────────────────┐              │
│   │  Claude Code (Orchestrator)              │              │
│   │  • Story decomposition                   │              │
│   │  • File operations                       │              │
│   │  • Git operations                        │              │
│   │  • Final validation                      │              │
│   └─────────────────┬───────────────────────┘              │
│                     │                                        │
│         ┌───────────┴───────────┐                          │
│         │   Sub-task Router     │                          │
│         └───────────┬───────────┘                          │
│                     │                                        │
│    ┌────────┬───────┴───────┬────────┬────────┐           │
│    ▼        ▼               ▼        ▼        ▼           │
│ ┌──────┐┌──────┐      ┌──────┐ ┌──────┐ ┌──────┐        │
│ │Gemini││ GPT  │      │ Qwen │ │DeepSk│ │ GLM  │        │
│ │Vision││ o3   │      │ Max  │ │ R1   │ │ 4    │        │
│ └──────┘└──────┘      └──────┘ └──────┘ └──────┘        │
│    │        │              │        │        │            │
│    ▼        ▼              ▼        ▼        ▼            │
│  Image   Reasoning      Code Gen  Math    Chinese        │
│  Tasks   Tasks          Tasks     Tasks   Tasks          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- Claude handles complex orchestration (its strength)
- Other LLMs used for their specialties
- Manageable scope
- Cost optimization for sub-tasks

**Cons:**
- Still requires API integration for each provider
- Sub-task results need to be integrated back
- Claude remains the bottleneck

**Effort**: 2-3 months, ~5k lines of code
**Recommendation**: ⚠️ Possible, but limited value

---

### Option C: LLM-as-Reviewer Pattern (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                    OPTION C: LLM-as-Reviewer                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   claude-loop.sh                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────────────────────────────────┐              │
│   │  Claude Code (Primary Implementation)    │              │
│   │  • Full story implementation             │              │
│   │  • All file/git operations               │              │
│   └─────────────────┬───────────────────────┘              │
│                     │                                        │
│                     ▼                                        │
│   ┌─────────────────────────────────────────┐              │
│   │  Multi-LLM Review Panel                  │              │
│   └─────────────────┬───────────────────────┘              │
│                     │                                        │
│    ┌────────────────┼────────────────┐                     │
│    ▼                ▼                ▼                     │
│ ┌──────┐      ┌──────┐         ┌──────┐                   │
│ │ GPT  │      │Gemini│         │DeepSk│                   │
│ │Review│      │Review│         │Review│                   │
│ └──────┘      └──────┘         └──────┘                   │
│    │                │                │                      │
│    └────────────────┴────────────────┘                     │
│                     │                                        │
│                     ▼                                        │
│          ┌─────────────────┐                               │
│          │ Consensus Check │                               │
│          └────────┬────────┘                               │
│                   │                                         │
│          ┌────────┴────────┐                               │
│          ▼                 ▼                               │
│    [All Approve]     [Issues Found]                        │
│          │                 │                               │
│          ▼                 ▼                               │
│       ✅ Pass        Claude Fixes                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- Claude does what it's best at (implementation)
- Other LLMs provide diverse perspectives
- Catches blind spots and bugs
- Easy to implement (just API calls)
- Graceful degradation (review is optional)
- Cost-effective (review is cheaper than implementation)

**Cons:**
- Other LLMs don't directly implement
- Review may disagree with Claude's approach

**Effort**: 2-4 weeks, ~2k lines of code
**Recommendation**: ✅ Recommended first step

---

### Option D: Provider Fallback Chain

```
┌─────────────────────────────────────────────────────────────┐
│                    OPTION D: Fallback Chain                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   claude-loop.sh                                            │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────────────────────────────────┐              │
│   │  Provider Chain (Priority Order)         │              │
│   │                                          │              │
│   │  1. Claude Code (default)                │              │
│   │     └── If rate limited or unavailable:  │              │
│   │  2. Gemini 2.0 Flash                     │              │
│   │     └── If rate limited or unavailable:  │              │
│   │  3. DeepSeek V3                          │              │
│   │     └── If rate limited or unavailable:  │              │
│   │  4. Qwen Max                             │              │
│   │                                          │              │
│   └─────────────────────────────────────────┘              │
│                                                              │
│   Note: Non-Claude providers use simplified                 │
│         prompt-only mode (no tool use)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- High availability
- Automatic failover
- Simple to implement

**Cons:**
- Non-Claude providers have degraded capabilities
- Different models may produce inconsistent results

**Effort**: 1-2 weeks, ~1k lines of code
**Recommendation**: ⚠️ Good for availability, not capability

---

## Recommended Phased Approach

### Phase 1: LLM-as-Reviewer (Option C) — 2-4 weeks
- Add multi-LLM review panel after each story
- Support: GPT-4o, Gemini 2.0, DeepSeek V3
- Consensus-based approval
- Optional (can be disabled)

### Phase 2: Specialized Workers (Option B subset) — 4-6 weeks
- Add vision analysis for VLMs (Gemini, GPT-4V)
- Add reasoning tasks for o3/DeepSeek-R1
- Keep Claude as orchestrator

### Phase 3: Provider Fallback (Option D) — 2-3 weeks
- Add failover chain for availability
- Simplified mode for non-Claude providers

### Phase 4 (Future): Full Abstraction — Only if demand warrants
- Build agent runtimes for other providers
- Consider using LangChain/AutoGen

---

## Provider Comparison

| Provider | Model | Strengths | Context | Cost (input/output) |
|----------|-------|-----------|---------|---------------------|
| Anthropic | Claude Opus 4.5 | Coding, reasoning, tools | 200k | $15/$75 per M |
| Anthropic | Claude Sonnet 4 | Balance of speed/quality | 200k | $3/$15 per M |
| OpenAI | GPT-4o | General, vision | 128k | $2.50/$10 per M |
| OpenAI | o3 | Deep reasoning | 200k | $10-$100+/M |
| Google | Gemini 2.0 Flash | Fast, vision, grounding | 1M | $0.075/$0.30 per M |
| Google | Gemini 2.0 Pro | Best Gemini quality | 2M | $1.25/$5 per M |
| Alibaba | Qwen Max | Chinese, coding | 128k | ~$1.40/$5.60 per M |
| DeepSeek | DeepSeek V3 | Coding, math | 64k | $0.27/$1.10 per M |
| DeepSeek | DeepSeek R1 | Reasoning (CoT) | 64k | $0.55/$2.19 per M |
| Zhipu | GLM-4 | Chinese, general | 128k | ~$1/$4 per M |

## User Stories (Phase 1)

1. **LLM-001**: Provider configuration (API keys, endpoints)
2. **LLM-002**: Multi-LLM review panel architecture
3. **LLM-003**: GPT-4o reviewer integration
4. **LLM-004**: Gemini 2.0 reviewer integration
5. **LLM-005**: DeepSeek V3 reviewer integration
6. **LLM-006**: Consensus engine for review results
7. **LLM-007**: Review feedback integration with Claude
8. **LLM-008**: Cost tracking per provider
9. **LLM-009**: Provider health monitoring
10. **LLM-010**: CLI flags for review configuration

## Questions for Discussion

1. **Which providers are priority?** (GPT, Gemini, DeepSeek seem most useful)
2. **Should review be mandatory or optional?** (Recommend optional)
3. **How to handle disagreements?** (Claude decides, or human decides?)
4. **Budget controls?** (Cap spending per provider?)
5. **Do you need VLA (Vision Language Agent) capabilities?** (For robotics/physical AI?)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key management complexity | Medium | Use keyring/secrets manager |
| Cost explosion with multiple providers | High | Budget caps, usage tracking |
| Inconsistent results across providers | Medium | Consensus voting, human override |
| Provider API changes | Low | Adapter pattern isolation |
| Rate limiting | Medium | Exponential backoff, fallback chain |

## Decision Required

Before proceeding, please confirm:
1. **Phase 1 approach** (LLM-as-Reviewer) acceptable?
2. **Priority providers** for initial integration?
3. **Budget constraints** for multi-provider usage?
4. **VLM/VLA requirements** (image/video analysis needs)?
