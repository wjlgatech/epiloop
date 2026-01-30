# Research-Loop Action Plan

**Document Version:** 1.0
**Created:** January 18, 2026
**Owner:** Wu (Human Lead) + AI (Claude Implementation Partner)
**Status:** Active

---

## Executive Summary

This action plan translates the deep research findings and architecture specification into concrete, time-bound deliverables. The plan spans 12 months and focuses on three pillars:

1. **Complete Core Implementation** - Finish PRD user stories US-009 through US-013
2. **Build ResearchBench** - Create the first comprehensive benchmark for research agents
3. **Establish Strategic Partnerships** - Academic (Stanford AIMI) and Industry (Exa, Tavily)

**Current Progress:** 8/13 user stories complete (62%). Core orchestration, synthesis, and quality control agents operational.

---

## 1. Immediate Actions (This Week: Jan 18-24, 2026)

### 1.1 ResearchBench Opportunity Analysis

| Action | Owner | Due | Deliverable | Success Metric |
|--------|-------|-----|-------------|----------------|
| Define ResearchBench evaluation dimensions | AI | Jan 19 | `docs/research-loop/RESEARCHBENCH_SPEC.md` | 7 dimensions specified with metrics |
| Draft initial benchmark dataset requirements | Wu | Jan 20 | Dataset specification document | 100 sample questions defined |
| Research existing benchmark infrastructure (SWE-bench, AgentBench) | AI | Jan 21 | Infrastructure comparison report | Build vs. fork decision made |
| Create ResearchBench GitHub repo skeleton | Wu | Jan 22 | GitHub repo with README | Repo public and documented |

**Why This Week:** First-mover advantage in research benchmarking. No comprehensive research agent benchmark exists - this is our strategic moat.

### 1.2 Meta-Learning: CER Implementation Kickoff

| Action | Owner | Due | Deliverable | Success Metric |
|--------|-------|-----|-------------|----------------|
| Design ExperienceMemory schema | AI | Jan 19 | `schemas/experience-memory.json` | Schema validated against CER paper requirements |
| Create experience compression algorithm spec | AI | Jan 20 | Algorithm design doc | Compression ratio target: 10:1 |
| Implement basic experience storage | AI | Jan 21 | `lib/experience_memory.py` | Store/retrieve operations working |
| Add similarity search for experience retrieval | AI | Jan 24 | Similarity search in experience_memory.py | k-NN retrieval in <100ms |

**Why This Week:** CER provides 51% improvement on WebArena. Training-free implementation means immediate value with minimal risk.

### 1.3 Partnership Preparation

| Action | Owner | Due | Deliverable | Success Metric |
|--------|-------|-----|-------------|----------------|
| Research Stanford AIMI Startup Affiliate Program | Wu | Jan 19 | Application requirements summary | Eligibility confirmed |
| Create Exa.ai API account and test integration | AI | Jan 20 | `lib/exa_search.py` with working tests | 5 successful API calls |
| Create Tavily API integration test | AI | Jan 20 | Verify existing Tavily integration | All search tests passing |
| Draft partnership pitch deck outline | Wu | Jan 22 | Pitch deck outline (10 slides) | Value proposition clear |

---

## 2. Short-Term Actions (Next 30 Days: Jan 25 - Feb 24, 2026)

### 2.1 Complete Remaining PRD Stories

| Story | Title | Owner | Start | Target Completion | Key Deliverables |
|-------|-------|-------|-------|-------------------|------------------|
| US-009 | Investment Research Adapter | AI | Jan 25 | Feb 1 | Yahoo Finance client, CoinGecko client, 3 analyst agents, mandatory disclaimers |
| US-010 | Research Report Generator | AI | Feb 1 | Feb 7 | Markdown reports, inline citations, confidence scores, executive summary |
| US-011 | Human Checkpoint System | AI | Feb 7 | Feb 10 | Checkpoint logic, audit logging, interactive CLI integration |
| US-012 | Prediction Tracking & Learning | AI | Feb 10 | Feb 17 | Prediction tracker, outcome tracker, learning feedback loop |
| US-013 | Integration Tests & Documentation | AI | Feb 17 | Feb 24 | Full test suite, README, usage guide |

**Dependency Chain:**
```
US-009 (Investment Adapter)
    |
    v
US-010 (Report Generator) <-- US-003 (Synthesizer), US-005 (Source Eval), US-006 (Fact Check)
    |
    v
US-011 (Human Checkpoint) <-- US-003 (Synthesizer)
    |
    v
US-012 (Prediction Tracking) <-- US-009, US-005
    |
    v
US-013 (Tests & Docs) <-- All above
```

**Risk Mitigation:**
- US-009 is complex (marked "opus" model) - allocate 7 days vs. typical 4
- US-010 has multiple dependencies - ensure all upstream stories fully validated before starting

### 2.2 Implement Contextual Experience Replay (CER)

| Milestone | Owner | Due | Deliverable | Success Metric |
|-----------|-------|-----|-------------|----------------|
| Experience storage operational | AI | Feb 1 | Production-ready experience_memory.py | 1000 experiences storable |
| Compression pipeline | AI | Feb 8 | Pattern extraction from experiences | 10:1 compression achieved |
| Retrieval integration | AI | Feb 15 | CER integrated into research synthesizer | Top-5 relevant experiences retrieved per query |
| A/B testing framework | AI | Feb 22 | With/without CER comparison | Measure improvement % |

**Expected Outcome:** 30-50% improvement in research quality for repeated domain queries.

### 2.3 Stanford AIMI Startup Affiliate Program Application

| Action | Owner | Due | Deliverable | Success Metric |
|--------|-------|-----|-------------|----------------|
| Complete application form | Wu | Feb 1 | Submitted application | Application confirmed received |
| Prepare demo video | Wu + AI | Feb 5 | 3-minute research-loop demo | Demonstrates AI-ML research use case |
| Draft research collaboration proposal | Wu | Feb 10 | 2-page proposal for Virtual Lab synergy | Concrete collaboration ideas |
| Follow-up with AIMI program manager | Wu | Feb 15 | Email/call scheduled | Contact established |

**Why Stanford AIMI:**
- Virtual Lab research directly relevant to multi-agent research systems
- Startup Affiliate tier provides access without major financial commitment
- Academic credibility for ResearchBench publication

---

## 3. Medium-Term Actions (Next 90 Days: Feb 25 - Apr 18, 2026)

### 3.1 Build ResearchBench v0.1

| Phase | Timeline | Deliverable | Success Metric |
|-------|----------|-------------|----------------|
| **Benchmark Design** | Feb 25 - Mar 7 | Complete benchmark specification | 7 evaluation dimensions with rubrics |
| **Dataset Creation** | Mar 8 - Mar 21 | 500 curated research questions | Questions span 5 domains |
| **Ground Truth Generation** | Mar 22 - Apr 4 | Expert-validated answers for 100 questions | Inter-annotator agreement > 0.8 |
| **Evaluation Harness** | Apr 5 - Apr 11 | Automated evaluation pipeline | Runs in <10 min per submission |
| **Baseline Results** | Apr 12 - Apr 18 | GPT-4, Claude, research-loop scores | Leaderboard populated |

**ResearchBench Evaluation Dimensions:**
1. Question Decomposition Quality (0-100)
2. Source Coverage Completeness (recall vs. expert source list)
3. Citation Accuracy (precision - are citations real and correct?)
4. Synthesis Coherence (human evaluation 1-5)
5. Gap Identification (F1 vs. expert-identified gaps)
6. Counterargument Discovery (recall of known counterarguments)
7. Confidence Calibration (ECE - expected calibration error)

### 3.2 Search API Partnerships (Exa, Tavily)

| Partner | Action | Owner | Due | Deliverable |
|---------|--------|-------|-----|-------------|
| **Exa.ai** | Establish API partnership | Wu | Mar 1 | Partnership agreement or upgraded API tier |
| **Exa.ai** | Integrate as primary academic search | AI | Mar 15 | `lib/exa_search.py` production-ready |
| **Exa.ai** | Publish integration blog post | Wu | Mar 30 | Blog post on Exa + research-loop |
| **Tavily** | Confirm SOC 2 requirements met | Wu | Mar 15 | Compliance documentation |
| **Tavily** | Optimize for 20-source aggregation | AI | Mar 30 | Multi-source search working |
| **SerpAPI** | Evaluate as backup provider | AI | Mar 15 | Comparison report |

**API Cost Projections (per 1000 research queries):**
| Provider | Cost | Capability |
|----------|------|------------|
| Exa.ai | ~$50 | 94.9% accuracy, academic focus |
| Tavily | ~$10 | SOC 2, 20 source aggregation |
| SerpAPI | ~$15 | Google results fallback |

**Recommendation:** Exa primary for academic/AI-ML, Tavily for general/investment, SerpAPI fallback.

### 3.3 LangChain Community Contribution

| Milestone | Owner | Due | Deliverable | Success Metric |
|-----------|-------|-----|-------------|----------------|
| Identify contribution opportunity | AI | Mar 1 | RFC or issue filed | Community feedback received |
| Develop research-loop integration | AI | Mar 15 | LangChain-compatible wrapper | Tests passing |
| Submit PR | Wu | Mar 30 | Pull request submitted | PR merged or feedback received |
| Write tutorial | Wu + AI | Apr 15 | Integration tutorial | Published on LangChain docs |

**Why LangChain:**
- 80K+ GitHub stars = massive visibility
- Industry-standard tool orchestration
- Positions research-loop as enterprise-ready

---

## 4. Strategic Initiatives (6-12 Months: Apr 2026 - Jan 2027)

### 4.1 Academic Partnership Development

| Quarter | Target | Action | Success Metric |
|---------|--------|--------|----------------|
| Q2 2026 | Stanford AIMI | Complete affiliate program enrollment | Access to AIMI resources |
| Q2 2026 | Berkeley BAIR | Apply to Open Research Commons affiliate | Membership approved |
| Q3 2026 | Princeton AI Lab | Apply to corporate affiliate program | Application submitted |
| Q3 2026 | First academic paper | Submit ResearchBench paper to NeurIPS/AAAI | Paper submitted |
| Q4 2026 | Research collaboration | Joint project with academic partner | Co-authored research |

**Academic Partnership Value:**
- Credibility for ResearchBench adoption
- Access to graduate student collaborators
- Publication venues for research-loop research
- Early access to cutting-edge research techniques

### 4.2 ResearchBench Public Release

| Milestone | Timeline | Deliverable | Success Metric |
|-----------|----------|-------------|----------------|
| Private beta | May 2026 | ResearchBench v0.5 to 10 research teams | 10 teams submitting results |
| Public leaderboard | Jul 2026 | Public benchmark website | 50+ submissions |
| Paper submission | Aug 2026 | NeurIPS/AAAI benchmark paper | Paper accepted |
| v1.0 release | Oct 2026 | Full public release with documentation | 100+ GitHub stars |

**ResearchBench Positioning:**
> "ResearchBench is to research agents what SWE-bench is to coding agents - the definitive evaluation standard."

### 4.3 Meta-Learning Agent Architecture

| Phase | Timeline | Deliverable | Success Metric |
|-------|----------|-------------|----------------|
| **CER Production** | May 2026 | Contextual Experience Replay in production | 30%+ improvement measured |
| **Self-Critique Loop** | Jul 2026 | Constitutional AI principles for research | Self-critique reducing errors |
| **Meta-Controller** | Sep 2026 | Orchestration layer choosing specialists | Improved agent selection accuracy |
| **Self-Play (Experimental)** | Nov 2026 | Question generator + research answerer | Closed-loop improvement |

**GVU Pattern Implementation:**
```
┌─────────────────────────────────────────────────────────────┐
│                    META-LEARNING ARCHITECTURE                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │    GENERATOR     │    │     VERIFIER     │               │
│  │  (Research       │ -> │  (Fact checker,  │               │
│  │   Synthesizer)   │    │   Devil's Adv.)  │               │
│  └──────────────────┘    └──────────────────┘               │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│                       v                                      │
│              ┌──────────────────┐                            │
│              │     UPDATER      │                            │
│              │  (Experience     │                            │
│              │   Memory + CER)  │                            │
│              └──────────────────┘                            │
│                       │                                      │
│                       v                                      │
│              Improved prompts, agent selection,              │
│              confidence calibration                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Key Decisions Needed

### 5.1 Which Search APIs to Prioritize

| Decision | Options | Recommendation | Rationale | Decision Needed By |
|----------|---------|----------------|-----------|-------------------|
| Primary academic search | Exa vs. Semantic Scholar | **Exa** | 94.9% accuracy, unified API | Jan 25, 2026 |
| Primary general search | Tavily vs. SerpAPI | **Tavily** | SOC 2, 20-source aggregation | Jan 25, 2026 |
| Backup provider | SerpAPI vs. DuckDuckGo | **SerpAPI** | More reliable, Google results | Feb 1, 2026 |

**Decision Owner:** Wu
**Input Required:** Cost analysis, API reliability testing results

### 5.2 ResearchBench Scope

| Decision | Options | Recommendation | Rationale | Decision Needed By |
|----------|---------|----------------|-----------|-------------------|
| Initial domain focus | Academic-only vs. Multi-domain | **Academic + AI-ML first** | Align with AIMI partnership | Feb 1, 2026 |
| Dataset size | 100 vs. 500 vs. 1000 questions | **500** | Balance between coverage and curation effort | Feb 15, 2026 |
| Evaluation method | Automated vs. Human vs. Hybrid | **Hybrid** | Automated for precision/recall, human for synthesis quality | Feb 15, 2026 |

**Decision Owner:** Wu
**Input Required:** Academic partner preferences, resource availability for human evaluation

### 5.3 Partnership Approach

| Decision | Options | Recommendation | Rationale | Decision Needed By |
|----------|---------|----------------|-----------|-------------------|
| First partnership focus | Academic vs. Industry | **Academic first** | Credibility for ResearchBench, lower barrier | Feb 1, 2026 |
| Stanford AIMI tier | Startup Affiliate vs. Full Corporate | **Startup Affiliate** | Lower cost, sufficient access | Feb 1, 2026 |
| Exa partnership level | Standard API vs. Partnership | **Explore partnership** | Volume discounts, co-marketing | Mar 1, 2026 |

**Decision Owner:** Wu
**Input Required:** Budget allocation, partnership terms

---

## 6. Success Metrics

### 6.1 ResearchBench Accuracy Targets

| Metric | Baseline (Current) | Q2 2026 Target | Q4 2026 Target | Measurement Method |
|--------|-------------------|----------------|----------------|-------------------|
| Question Decomposition | Not measured | 75% | 85% | Expert evaluation |
| Source Coverage Recall | Not measured | 60% | 80% | vs. expert source list |
| Citation Accuracy | 83%* (industry avg) | 90% | 95% | Automated + human verification |
| Synthesis Coherence | Not measured | 3.5/5 | 4.2/5 | Human evaluation (5-point scale) |
| Gap Identification F1 | Not measured | 0.50 | 0.70 | vs. expert-identified gaps |
| Confidence Calibration (ECE) | Not measured | 0.15 | 0.10 | Expected calibration error |

*Industry average: existing tools hallucinate 17-47% of citations

### 6.2 Partnership Milestones

| Partnership | Q1 2026 | Q2 2026 | Q3 2026 | Q4 2026 |
|-------------|---------|---------|---------|---------|
| Stanford AIMI | Application submitted | Affiliate status active | Joint research initiated | Paper co-authored |
| Exa.ai | API integration complete | Partnership agreement | Co-marketing activity | Volume discount active |
| Tavily | Integration verified | SOC 2 compliance confirmed | Production usage | - |
| Berkeley BAIR | - | Application submitted | Affiliate status | - |
| LangChain | Contribution identified | PR submitted | PR merged | Integration featured |

### 6.3 Revenue Targets from research-loop

| Metric | Q1 2026 | Q2 2026 | Q3 2026 | Q4 2026 |
|--------|---------|---------|---------|---------|
| Internal usage (queries/month) | 500 | 2,000 | 5,000 | 10,000 |
| External beta users | 0 | 10 | 50 | 200 |
| MRR (if monetized) | $0 | $0 | $500 | $5,000 |
| Cost per query | $2.50 | $1.50 | $1.00 | $0.75 |

**Revenue Strategy Options:**
1. **SaaS**: research-loop as service ($99/mo for researchers)
2. **API**: research-loop API access ($0.50/query)
3. **Enterprise**: On-premise deployment ($50K+ ARR)
4. **Open-core**: Core open source, premium features paid

**Decision Required:** Monetization strategy by Q3 2026

---

## 7. Risk Mitigation

### 7.1 What If ResearchBench Doesn't Gain Traction?

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Academic disinterest | Medium | High | Partner with AIMI/BAIR early, get endorsement |
| Industry adoption slow | Medium | Medium | Focus on enterprise pain points, not academic metrics |
| Better benchmark emerges | Low | High | Move fast, establish first-mover advantage |
| Insufficient ground truth quality | Medium | High | Invest in expert annotation, inter-annotator agreement |

**Contingency Plan:**
- If no academic traction by Q3 2026: Pivot to industry-focused benchmark (enterprise research assistant evaluation)
- If better benchmark emerges: Contribute to that benchmark rather than compete

### 7.2 Competition Analysis

| Competitor | Threat Level | Their Advantage | Our Advantage | Response Strategy |
|------------|--------------|-----------------|---------------|-------------------|
| **Perplexity** | High | $73M funding, user base | Deep customization, meta-learning | Focus on enterprise/research, not consumer |
| **Elicit** | High | Academic focus, user trust | Broader domains, investment research | Differentiate on synthesis quality, not just search |
| **GPT-Researcher** | Medium | Open source, community | Quality control, fact-checking | Contribute to ecosystem, position as "enterprise GPT-Researcher" |
| **Consensus** | Medium | Medical/scientific focus | Multi-domain, investment research | Avoid direct competition in medical |
| **Claude/GPT native** | High | Direct LLM access | Specialization, benchmark, CER | Stay ahead on research-specific capabilities |

**Competitive Moat Building:**
1. **ResearchBench** - Own the evaluation standard
2. **CER/Meta-learning** - Performance advantage
3. **Academic partnerships** - Credibility and research access
4. **Domain adapters** - Specialized vertical solutions

### 7.3 Technical Risks

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| API rate limits/costs | High | Medium | Multi-provider strategy, caching, rate limiting |
| LLM hallucination in synthesis | Medium | High | Fact-checker, multi-source requirement, confidence calibration |
| CER not improving as expected | Medium | Medium | A/B testing, graceful fallback to non-CER |
| Search API provider changes pricing | Medium | Medium | Multi-provider redundancy, negotiate volume discounts |
| Investment research liability | Medium | High | Mandatory disclaimers, never claim to be financial advice |

**Technical Risk Budget:**
- Allocate 20% of development time to risk mitigation and testing
- Maintain 3 search provider integrations at all times
- Never deploy investment features without legal disclaimer review

---

## 8. Resource Allocation

### 8.1 Time Allocation (Next 90 Days)

| Activity | Wu Time | AI Time | Total Hours |
|----------|---------|---------|-------------|
| PRD completion (US-009 to US-013) | 10% | 60% | 120 |
| ResearchBench design & dataset | 30% | 20% | 100 |
| Partnership development | 40% | 5% | 90 |
| CER implementation | 5% | 15% | 40 |
| Project management & reviews | 15% | 0% | 30 |

### 8.2 Budget Allocation (2026)

| Category | Q1 | Q2 | Q3 | Q4 | Annual |
|----------|----|----|----|----|--------|
| API costs (search, LLM) | $500 | $1,500 | $3,000 | $5,000 | $10,000 |
| Academic partnerships | $0 | $2,500 | $2,500 | $2,500 | $7,500 |
| Annotation/ground truth | $0 | $1,000 | $2,000 | $1,000 | $4,000 |
| Infrastructure | $200 | $400 | $600 | $800 | $2,000 |
| Marketing/events | $0 | $500 | $1,000 | $1,500 | $3,000 |
| **Total** | **$700** | **$5,900** | **$9,100** | **$10,800** | **$26,500** |

---

## 9. Weekly Review Cadence

### Review Schedule

| Day | Activity | Participants | Duration |
|-----|----------|--------------|----------|
| Monday | Sprint planning | Wu, AI | 30 min |
| Wednesday | Technical deep-dive | AI (async report) | - |
| Friday | Progress review & blockers | Wu, AI | 30 min |

### Key Questions for Weekly Review

1. Are we on track for current sprint deliverables?
2. Have any risks materialized? New risks identified?
3. Partnership progress update
4. ResearchBench milestone status
5. Blockers requiring human decision

---

## Appendix A: Quick Reference - What's Done vs. What's Left

### Completed (8/13 User Stories)

| ID | Title | Status |
|----|-------|--------|
| US-001 | Core Research Orchestrator | DONE |
| US-002 | Web Search Integration | DONE |
| US-003 | Lead Researcher Agent | DONE |
| US-004 | Domain Expert Agents | DONE |
| US-005 | Source Credibility Evaluator | DONE |
| US-006 | Fact Checker Agent | DONE |
| US-007 | Devil's Advocate Agent | DONE |
| US-008 | AI-ML Research Adapter | DONE |

### Remaining (5/13 User Stories)

| ID | Title | Est. Effort | Priority |
|----|-------|-------------|----------|
| US-009 | Investment Research Adapter | 7 days | P1 |
| US-010 | Research Report Generator | 5 days | P1 |
| US-011 | Human Checkpoint System | 3 days | P2 |
| US-012 | Prediction Tracking & Learning | 5 days | P2 |
| US-013 | Integration Tests & Documentation | 5 days | P3 |

---

## Appendix B: Contact Information

### Academic Partners

| Organization | Program | Contact Method | Status |
|--------------|---------|----------------|--------|
| Stanford AIMI | Startup Affiliate | aimi.stanford.edu/industry-affiliates | Research needed |
| Berkeley BAIR | Open Research Commons | bcommons.berkeley.edu | Research needed |
| Princeton AI Lab | Corporate Affiliate | Apply 2025-26 cycle | Research needed |

### Industry Partners

| Company | API/Service | Contact Method | Status |
|---------|-------------|----------------|--------|
| Exa.ai | Research API | exa.ai | API key obtained |
| Tavily | Search API | tavily.com | API key obtained |
| Anthropic | MCP Protocol | anthropic.com | MCP adopted in claude-loop |

---

## Appendix C: Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 18, 2026 | Wu + Claude | Initial comprehensive action plan |

---

*This document should be reviewed and updated weekly during the sprint review. Major updates require version increment.*
