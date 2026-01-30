# Research-Loop: Agentic Research Team
## Architectural Specification v0.1

**Status:** Draft
**Author:** Wu + Claude
**Date:** January 2026
**Built on:** claude-loop v3.0 orchestration layer

---

## Executive Summary

Research-loop is an autonomous multi-agent research system that coordinates specialized AI agents to investigate complex questions, synthesize findings, and produce verified research reports with citations and confidence scores.

**Core Thesis:** The same evaluation and meta-reasoning patterns that make claude-loop effective for coding can be applied to knowledge work—with the added challenge of verifying truth in a world of misinformation.

---

## 1. System Architecture

### 1.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESEARCH-LOOP ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ORCHESTRATION LAYER                           │   │
│  │                    (inherited from claude-loop)                      │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │   Research   │  │    State     │  │   Quality    │              │   │
│  │  │   Planner    │  │   Manager    │  │    Gates     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         AGENT TEAM LAYER                             │   │
│  │                                                                      │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │  Domain    │ │  Academic  │ │   Market   │ │   News     │       │   │
│  │  │  Expert    │ │  Scanner   │ │  Analyst   │ │  Tracker   │       │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │   │
│  │                                                                      │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐                       │   │
│  │  │   Fact     │ │  Devil's   │ │  Source    │                       │   │
│  │  │  Checker   │ │  Advocate  │ │  Evaluator │                       │   │
│  │  └────────────┘ └────────────┘ └────────────┘                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        DATA SOURCE LAYER                             │   │
│  │                                                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │  Web     │ │  arXiv   │ │  SEC     │ │  GitHub  │ │  Patents │ │   │
│  │  │  Search  │ │          │ │  EDGAR   │ │          │ │          │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  │                                                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │   │
│  │  │  News    │ │  Company │ │  Crypto  │ │  Custom  │              │   │
│  │  │  APIs    │ │  DBs     │ │  APIs    │ │  Sources │              │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MEMORY LAYER                                 │   │
│  │               (domain-partitioned, inherited from claude-loop)       │   │
│  │                                                                      │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │   │
│  │  │  Source        │  │  Finding       │  │  Correction    │        │   │
│  │  │  Credibility   │  │  History       │  │  Learning      │        │   │
│  │  │  Store         │  │  Store         │  │  Store         │        │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Research Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         RESEARCH EXECUTION FLOW                           │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. QUESTION DECOMPOSITION                                                │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  "What are the most promising AI approaches to protein folding?" │  │
│     └─────────────────────────────────────────────────────────────────┘  │
│                              │                                            │
│                              ▼                                            │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  Sub-questions (auto-generated):                                 │  │
│     │  Q1: What ML architectures are used? (Technical)                 │  │
│     │  Q2: Who are the key players? (Market)                           │  │
│     │  Q3: What are recent breakthroughs? (News/Academic)              │  │
│     │  Q4: What are current limitations? (Academic)                    │  │
│     │  Q5: What's the commercial landscape? (Market)                   │  │
│     └─────────────────────────────────────────────────────────────────┘  │
│                              │                                            │
│  2. PARALLEL RESEARCH        ▼                                            │
│     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│     │ Agent 1 │ │ Agent 2 │ │ Agent 3 │ │ Agent 4 │ │ Agent 5 │        │
│     │   Q1    │ │   Q2    │ │   Q3    │ │   Q4    │ │   Q5    │        │
│     └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │
│          │           │           │           │           │              │
│          └───────────┴───────────┴───────────┴───────────┘              │
│                              │                                            │
│  3. SYNTHESIS & VERIFICATION ▼                                            │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  Lead Researcher synthesizes findings                            │  │
│     │  Fact Checker verifies key claims                                │  │
│     │  Devil's Advocate challenges conclusions                         │  │
│     │  Source Evaluator scores credibility                             │  │
│     └─────────────────────────────────────────────────────────────────┘  │
│                              │                                            │
│  4. HUMAN CHECKPOINT         ▼                                            │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  [Review] Key findings with confidence scores                    │  │
│     │  [Approve] / [Request more depth] / [Redirect]                   │  │
│     └─────────────────────────────────────────────────────────────────┘  │
│                              │                                            │
│  5. OUTPUT GENERATION        ▼                                            │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  Structured report with:                                         │  │
│     │  - Executive summary                                             │  │
│     │  - Detailed findings by sub-question                             │  │
│     │  - Source citations with credibility scores                      │  │
│     │  - Confidence levels per claim                                   │  │
│     │  - Identified gaps / areas needing human review                  │  │
│     └─────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Specifications

### 2.1 Lead Researcher (Orchestrator)

**Role:** Decomposes questions, delegates to specialists, synthesizes findings, identifies gaps.

**Capabilities:**
- Question decomposition into sub-questions
- Agent selection based on question type
- Synthesis of multi-agent findings
- Gap identification and follow-up questions
- Conflict resolution between agents

**Prompt Template:**
```markdown
You are the Lead Researcher orchestrating a research team.

RESEARCH QUESTION: {{question}}

Your tasks:
1. Break this into 3-7 specific, answerable sub-questions
2. Assign each sub-question to the most appropriate specialist
3. After receiving findings, synthesize into coherent narrative
4. Identify contradictions, gaps, and areas needing verification
5. Assign confidence score (0-100) to each major finding

Output format:
- Sub-questions with agent assignments
- Synthesis with citations
- Confidence scores with justification
- Identified gaps
```

### 2.2 Domain Expert Agents

#### 2.2.1 Technical Deep-Diver

**Focus:** Code, APIs, technical documentation, implementation details

**Data Sources:** GitHub, Stack Overflow, official docs, technical blogs

**Output:** Technical architecture summaries, code examples, implementation patterns

#### 2.2.2 Academic Scanner

**Focus:** Peer-reviewed research, preprints, citations

**Data Sources:** arXiv, PubMed, Google Scholar, Semantic Scholar

**Output:** Paper summaries, citation networks, methodology comparisons

#### 2.2.3 Market Analyst

**Focus:** Companies, products, pricing, competitive landscape

**Data Sources:** Crunchbase, company websites, press releases, pricing pages

**Output:** Market maps, competitive analysis, funding data

#### 2.2.4 News/Trends Tracker

**Focus:** Recent developments, announcements, industry movements

**Data Sources:** News APIs, Twitter/X, industry newsletters, press releases

**Output:** Timeline of developments, trend analysis, key announcements

### 2.3 Quality Control Agents

#### 2.3.1 Fact Checker

**Role:** Verifies specific claims against multiple sources

**Method:**
1. Extract factual claims from findings
2. Search for corroborating/contradicting evidence
3. Flag claims with <2 independent sources
4. Identify potential misinformation patterns

**Output:** Claim verification report with confidence scores

#### 2.3.2 Devil's Advocate

**Role:** Challenges conclusions, finds counterarguments

**Method:**
1. Identify main conclusions
2. Search for contradicting evidence
3. Propose alternative interpretations
4. Rate strength of counterarguments

**Output:** Counterargument report, conclusion stress-test

#### 2.3.3 Source Evaluator

**Role:** Assesses credibility of sources

**Scoring Criteria:**
- Domain authority (academic, news, blog, forum)
- Author credentials (if identifiable)
- Publication date (recency)
- Citation count (for academic)
- Cross-reference frequency
- Known bias indicators

**Output:** Source credibility scores (0-100) with justification

---

## 3. Memory Architecture

### 3.1 Source Credibility Store

Tracks reliability of sources over time based on:
- Fact-check success rate
- Human corrections
- Cross-reference accuracy

```python
class SourceCredibility:
    source_domain: str           # e.g., "arxiv.org", "medium.com"
    credibility_score: float     # 0-100, updated over time
    verification_count: int      # times verified
    correction_count: int        # times human corrected
    last_updated: datetime
    domain_specialties: list     # ["ml", "biology", "business"]
```

### 3.2 Finding History Store

Persists research findings for:
- Avoiding redundant research
- Building on previous work
- Tracking evolving understanding

```python
class ResearchFinding:
    finding_id: str
    question: str
    answer: str
    confidence: float
    sources: list[Source]
    created_at: datetime
    verified_by_human: bool
    corrections: list[Correction]
    domain: str                  # "ai-ml", "health", "market"
```

### 3.3 Correction Learning Store

Captures human corrections to improve future research:

```python
class Correction:
    original_finding: str
    corrected_finding: str
    correction_type: str         # "factual", "interpretation", "source"
    human_explanation: str
    applied_to_model: bool
```

---

## 4. Quality Gates

### 4.1 Pre-Output Gates

| Gate | Threshold | Action if Failed |
|------|-----------|------------------|
| Source diversity | ≥3 independent sources per major claim | Request more research |
| Confidence minimum | ≥60% on key findings | Flag for human review |
| Contradiction check | <2 unresolved contradictions | Escalate to Devil's Advocate |
| Recency check | Primary sources <2 years old | Flag as potentially outdated |
| Credibility floor | Average source score ≥50 | Request higher-quality sources |

### 4.2 Human Checkpoints

**Mandatory human review for:**
- Health/medical claims (always)
- Financial recommendations (always)
- Confidence <70% on key findings
- Contradictions between agents
- Novel claims not in training data

---

## 5. Domain Adapters

### 5.1 AI-ML Research Adapter

**Specialized Sources:**
- arXiv (cs.AI, cs.LG, cs.CL, cs.CV)
- Papers With Code
- Hugging Face model cards
- GitHub trending repos
- ML conferences (NeurIPS, ICML, ICLR)

**Domain-Specific Agents:**
- **Benchmark Analyst:** Tracks SOTA on standard benchmarks
- **Architecture Expert:** Analyzes model architectures
- **Scaling Laws Tracker:** Monitors compute/data scaling trends

**Specialized Prompts:**
```markdown
When researching AI-ML topics:
- Always check Papers With Code for SOTA benchmarks
- Distinguish between peer-reviewed and preprint claims
- Note compute requirements and reproducibility
- Track author affiliations (academic vs. industry)
- Identify potential benchmark gaming
```

**Quality Gates (AI-ML specific):**
- Reproducibility score (code available? data available?)
- Benchmark validity (standard splits? fair comparison?)
- Compute accessibility (can average researcher replicate?)

### 5.2 Investment Research Adapter (Stocks, Crypto, Real Estate)

**The Challenge Query:**
> "Given $10K capital, can you identify opportunities to reach $100K within 3 months?"

**Specialized Sources:**

| Asset Class | Data Sources |
|-------------|--------------|
| **Stocks** | SEC EDGAR (10-K, 10-Q, 8-K filings), Yahoo Finance, Finviz, Seeking Alpha, earnings transcripts |
| **Crypto** | CoinGecko, Messari, Glassnode (on-chain), DeFiLlama, token unlock calendars, GitHub activity |
| **Real Estate** | Zillow, Redfin, CoStar, FRED (economic indicators), local MLS data, REITs (SEC filings) |
| **Cross-Asset** | TradingView, macro indicators (Fed, Treasury), sentiment (Fear & Greed Index) |

**Domain-Specific Agents:**

- **Fundamental Analyst:** Evaluates financials, valuations, competitive moats
- **Technical Analyst:** Chart patterns, momentum indicators, support/resistance
- **Sentiment Tracker:** Social media sentiment, news sentiment, insider activity
- **Risk Assessor:** Volatility analysis, correlation, max drawdown scenarios
- **Macro Analyst:** Interest rates, inflation, sector rotation, liquidity conditions
- **Catalyst Hunter:** Earnings dates, token unlocks, regulatory events, M&A rumors

**Specialized Prompts:**
```markdown
When researching investment opportunities:
- ALWAYS note the timeframe and risk profile
- Distinguish between speculation and investment
- Include historical performance AND forward catalysts
- Note market cap, liquidity, and position sizing implications
- Identify potential risks (regulatory, competition, macro)
- Track insider/whale activity where available
- NEVER guarantee returns - all projections are probabilistic
- Include bear case, base case, and bull case scenarios
```

**Investment-Specific Quality Gates:**

| Gate | Threshold | Action |
|------|-----------|--------|
| Source recency | Data <24h for trading, <7d for investing | Flag stale data |
| Confirmation bias check | ≥1 bearish source per bullish thesis | Require Devil's Advocate |
| Risk disclosure | Risk section present | Mandatory |
| Liquidity check | Can enter/exit position in target size | Flag illiquid assets |
| Backtesting caveat | Historical ≠ future | Mandatory disclaimer |

**Risk-Adjusted Research Framework:**

```
┌─────────────────────────────────────────────────────────────────┐
│              INVESTMENT RESEARCH OUTPUT STRUCTURE               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. OPPORTUNITY IDENTIFICATION                                   │
│     └── Asset, thesis summary, key catalysts                    │
│                                                                  │
│  2. FUNDAMENTAL ANALYSIS                                         │
│     └── Valuation, financials, competitive position             │
│                                                                  │
│  3. TECHNICAL ANALYSIS                                           │
│     └── Entry zones, targets, stop-loss levels                  │
│                                                                  │
│  4. SENTIMENT & FLOW ANALYSIS                                    │
│     └── Social sentiment, institutional flow, insider activity  │
│                                                                  │
│  5. RISK ASSESSMENT                                              │
│     ├── Bear case scenario (what could go wrong)                │
│     ├── Max drawdown estimate                                    │
│     ├── Correlation to broader market                           │
│     └── Position sizing recommendation                          │
│                                                                  │
│  6. SCENARIO ANALYSIS                                            │
│     ├── Bull case: $X (+Y%) - probability Z%                    │
│     ├── Base case: $X (+Y%) - probability Z%                    │
│     └── Bear case: $X (-Y%) - probability Z%                    │
│                                                                  │
│  7. ACTION PLAN                                                  │
│     ├── Entry strategy (DCA, limit orders, etc.)                │
│     ├── Exit strategy (targets, trailing stops)                 │
│     └── Rebalancing triggers                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**10K → 100K Challenge Framework:**

To achieve 10x in 3 months requires either:
1. **High-conviction concentrated bets** (very high risk)
2. **Leveraged positions** (liquidation risk)
3. **Options/derivatives** (time decay, complexity)
4. **Early-stage crypto** (extreme volatility)

Research-loop will:
- Identify highest asymmetric risk/reward opportunities
- Provide probability-weighted expected returns
- Model portfolio allocation across risk levels
- Track and learn from outcomes

**Sample Portfolio Research Output:**
```
10K → 100K AGGRESSIVE GROWTH PORTFOLIO (3-month horizon)

Risk Warning: This requires 10x return (900% gain).
Historical success rate for this target: <5%
Maximum recommended allocation: Money you can afford to lose entirely

PROPOSED ALLOCATION:
├── 40% High-conviction altcoins (4x-10x potential)
│   └── [Specific tokens with catalyst analysis]
├── 30% Options plays on volatile stocks (10x+ potential)
│   └── [Specific setups with Greeks analysis]
├── 20% Small-cap momentum stocks (2x-5x potential)
│   └── [Specific tickers with technical setups]
└── 10% Cash reserve for opportunities

Expected Value Analysis:
- P(10x): 3-5%
- P(5x): 10-15%
- P(2x): 25-30%
- P(breakeven): 15-20%
- P(50% loss): 20-25%
- P(total loss): 10-15%

Confidence: 45% (high uncertainty due to aggressive target)
```

**CRITICAL SAFETY RULES:**
```
1. All investment research outputs MUST include disclaimer:
   "This is research synthesis, NOT financial advice.
   Past performance does not guarantee future results.
   Never invest more than you can afford to lose.
   Consult a licensed financial advisor before making investment decisions."

2. NEVER claim guaranteed returns or "sure things"

3. ALWAYS include risk assessment and bear case

4. For 10x targets, ALWAYS note the low probability of success

5. Track predictions and learn from outcomes (calibration)
```

**Backtesting & Learning:**
- Record all recommendations with timestamps
- Track actual outcomes vs. predictions
- Calculate hit rate, average return, Sharpe ratio
- Feed results back into agent improvement
- Identify which signals/sources had predictive value

---

## 6. Testing Use Cases

### 6.1 AI-ML Research Use Case

**Test Query:**
> "What are the most promising approaches to achieving sample-efficient reinforcement learning for robotics, and what are their current limitations?"

**Expected Research Flow:**

```
1. QUESTION DECOMPOSITION (Lead Researcher)
   ├── Q1: What RL architectures show best sample efficiency? (Academic)
   ├── Q2: How are simulation-to-real transfer methods performing? (Technical)
   ├── Q3: Which companies/labs are leading? (Market)
   ├── Q4: What are the benchmark results? (Technical)
   └── Q5: What fundamental limitations exist? (Academic)

2. PARALLEL RESEARCH
   ├── Academic Scanner → arXiv papers on model-based RL, world models
   ├── Technical Deep-Diver → GitHub repos, implementation details
   ├── Market Analyst → Companies (Covariant, Physical Intelligence, etc.)
   └── Benchmark Analyst → Results on DMControl, Meta-World

3. SYNTHESIS
   Key findings:
   - World models (Dreamer v3, TD-MPC2) showing 10-100x improvement
   - Sim-to-real gap remains significant challenge
   - Foundation models for robotics emerging (RT-2, Octo)

4. VERIFICATION
   Fact Checker: Verify benchmark numbers against papers
   Devil's Advocate: Challenge "10-100x" claim specificity
   Source Evaluator: Rate arXiv vs peer-reviewed

5. OUTPUT
   Report with:
   - Ranked approaches by sample efficiency
   - Current SOTA benchmarks
   - Key limitations (sim-to-real, generalization)
   - Commercial landscape
   - Research gaps
   - Confidence: 78% (strong academic basis, limited real-world validation)
```

**Acceptance Criteria:**
- [ ] Identifies ≥5 distinct approaches with citations
- [ ] Includes benchmark numbers from Papers With Code
- [ ] Distinguishes simulation vs. real-world results
- [ ] Names ≥3 leading research groups/companies
- [ ] Identifies ≥3 specific limitations
- [ ] All claims have ≥2 sources
- [ ] Confidence scores provided for each major finding

---

### 6.2 Investment Research Use Case: The 10K → 100K Challenge

**Test Query:**
> "Given $10K capital, identify the highest asymmetric risk/reward opportunities to reach $100K within 3 months. Include stocks, crypto, and options strategies with specific entry/exit criteria."

**Expected Research Flow:**

```
1. QUESTION DECOMPOSITION (Lead Researcher)
   ├── Q1: What crypto tokens have upcoming catalysts? (Crypto Analyst)
   ├── Q2: What small-cap stocks show momentum + catalysts? (Fundamental + Technical)
   ├── Q3: What options setups offer 10x+ potential? (Technical + Risk)
   ├── Q4: What are current macro conditions? (Macro Analyst)
   ├── Q5: What could cause total loss? (Risk Assessor + Devil's Advocate)
   └── Q6: What's the probability-weighted expected return? (Lead Researcher)

2. PARALLEL RESEARCH
   ├── Crypto Analyst → Token unlocks, protocol upgrades, on-chain metrics
   │   Sources: CoinGecko, Messari, DeFiLlama, Token Unlocks calendar
   ├── Fundamental Analyst → Small-cap earnings surprises, insider buying
   │   Sources: SEC EDGAR, Finviz screeners, Seeking Alpha
   ├── Technical Analyst → Breakout setups, momentum screens
   │   Sources: TradingView, chart patterns, volume analysis
   ├── Sentiment Tracker → Social buzz, whale movements
   │   Sources: LunarCrush, Santiment, unusual options activity
   ├── Macro Analyst → Fed policy, liquidity conditions, risk appetite
   │   Sources: FRED, Treasury data, Fear & Greed Index
   └── Risk Assessor → Volatility, correlation, max drawdown scenarios
       Sources: Historical data, options implied vol

3. SYNTHESIS
   Key opportunities identified:
   - [Specific crypto token] - catalyst: [X], potential: 5-15x
   - [Specific stock] - catalyst: [earnings/FDA/etc], potential: 3-5x
   - [Options strategy] - setup: [specifics], potential: 10x+

   Portfolio allocation recommendation:
   - 40% crypto (highest upside, highest risk)
   - 30% options (defined risk, leverage)
   - 20% momentum stocks (lower risk, lower upside)
   - 10% cash (for dips/opportunities)

4. VERIFICATION (ENHANCED for investment)
   Fact Checker:
   - Verify catalyst dates (earnings, token unlocks)
   - Cross-reference price/volume data
   - Check for recent news affecting thesis
   Devil's Advocate:
   - Present bear case for each position
   - Identify correlation risks (all positions down together)
   - Challenge probability estimates
   Risk Assessor:
   - Model worst-case scenarios
   - Estimate probability of total loss
   - Recommend position sizing

5. HUMAN CHECKPOINT (MANDATORY for investment)
   "Research complete. Key findings:
   - 3 high-conviction opportunities identified
   - Estimated probability of 10x: 3-5%
   - Estimated probability of total loss: 10-15%
   - Risk-adjusted expected value: +X%

   ⚠️  This is aggressive speculation, not investment advice.
   Proceed to detailed report?"

6. OUTPUT
   Report with:
   ┌─────────────────────────────────────────────────┐
   │  10K → 100K AGGRESSIVE PORTFOLIO REPORT         │
   ├─────────────────────────────────────────────────┤
   │  OPPORTUNITY 1: [Token/Stock/Option]            │
   │  - Thesis: [1-2 sentences]                      │
   │  - Catalyst: [specific event + date]            │
   │  - Entry: [price/conditions]                    │
   │  - Target: [price] (+X%)                        │
   │  - Stop-loss: [price] (-Y%)                     │
   │  - Position size: $Z (Z% of portfolio)          │
   │  - Bull/Base/Bear scenarios with probabilities  │
   │  - Key risks                                    │
   │                                                 │
   │  [Repeat for each opportunity]                  │
   │                                                 │
   │  PORTFOLIO SUMMARY                              │
   │  - Total expected return (probability-weighted) │
   │  - Max drawdown estimate                        │
   │  - Correlation analysis                         │
   │  - Rebalancing triggers                         │
   │                                                 │
   │  RISK DISCLOSURE                                │
   │  - Probability of 10x: X%                       │
   │  - Probability of 2x: Y%                        │
   │  - Probability of loss: Z%                      │
   │  - Probability of total loss: W%                │
   │                                                 │
   │  ⚠️  MANDATORY DISCLAIMER                       │
   │  This is research synthesis, NOT financial      │
   │  advice. [Full disclaimer text]                 │
   └─────────────────────────────────────────────────┘

   Confidence: 35% (high uncertainty due to aggressive target)
```

**Acceptance Criteria:**
- [ ] Identifies ≥3 specific opportunities with tickers/tokens
- [ ] Each opportunity has entry price, target, stop-loss
- [ ] Catalyst dates are verified and cited
- [ ] Bull/base/bear scenarios with probability estimates
- [ ] Portfolio allocation with position sizing rationale
- [ ] Devil's Advocate bear case for each position
- [ ] Correlation analysis (what if everything drops together?)
- [ ] Max drawdown estimate for portfolio
- [ ] Probability distribution for outcomes
- [ ] NO guaranteed return claims
- [ ] Full disclaimer present
- [ ] All data sources cited
- [ ] Confidence score reflects high uncertainty

**Backtesting Protocol (Post-Research):**
- [ ] Record all recommendations with timestamps
- [ ] Track prices at +1 week, +1 month, +3 months
- [ ] Calculate actual returns vs. predicted
- [ ] Identify which signals had predictive value
- [ ] Feed learnings back to improve future research

---

## 7. Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

**Inherit from claude-loop:**
- [ ] Orchestration layer
- [ ] State management
- [ ] Memory architecture
- [ ] Quality gate framework

**Build new:**
- [ ] Research question decomposition
- [ ] Basic web search integration (Tavily or Exa)
- [ ] Lead Researcher agent
- [ ] Simple fact-checker

**Deliverable:** Can answer simple research questions with citations

### Phase 2: Specialists (Weeks 3-4)

**Add agents:**
- [ ] Academic Scanner (arXiv, PubMed integration)
- [ ] Technical Deep-Diver (GitHub, docs)
- [ ] Market Analyst (web search focused)
- [ ] Source Evaluator

**Add memory:**
- [ ] Source credibility store
- [ ] Finding history store

**Deliverable:** Can perform domain-specific research with quality scoring

### Phase 3: Domain Adapters (Weeks 5-6)

**Build adapters:**
- [ ] AI-ML adapter (Papers With Code, HuggingFace)
- [ ] Investment adapter (SEC EDGAR, CoinGecko, Yahoo Finance)

**Add agents:**
- [ ] Devil's Advocate
- [ ] Domain-specific specialists

**Quality:**
- [ ] Domain-specific quality gates
- [ ] Human checkpoint system

**Deliverable:** Full test use cases pass acceptance criteria

### Phase 4: Polish & Learn (Weeks 7-8)

**Improvements:**
- [ ] Correction learning pipeline
- [ ] Report generation templates
- [ ] Dashboard integration
- [ ] Performance optimization

**Testing:**
- [ ] 10 AI-ML queries with human evaluation
- [ ] 10 Health queries with human evaluation
- [ ] Measure accuracy, completeness, safety

**Deliverable:** Production-ready for internal use

---

## 8. Success Metrics

### Accuracy Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Factual accuracy | ≥90% | Human verification of claims |
| Source quality | ≥70 avg credibility | Source Evaluator scores |
| Completeness | ≥80% | Key aspects covered per human review |
| Contradiction rate | <10% | Unresolved contradictions in output |

### Safety Metrics (Health domain)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Disclaimer presence | 100% | Automated check |
| Medical advice detection | 0 instances | Content filter |
| Study type accuracy | 100% | Human verification |
| Conflict disclosure | 100% | Automated extraction |

### Efficiency Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Research time | <15 min typical | End-to-end timer |
| Cost per query | <$2 typical | API cost tracking |
| Human review time | <5 min typical | Time-on-task |

---

## 9. Risk Mitigation

### Hallucination Risk

**Mitigations:**
- Multiple source requirement for claims
- Fact-checker agent verification
- Confidence scores expose uncertainty
- Human checkpoint for low-confidence findings

### Misinformation Amplification

**Mitigations:**
- Source credibility scoring
- Known misinformation source blocklist
- Cross-reference requirement
- Devil's Advocate counterarguments

### Health Misinformation (Critical)

**Mitigations:**
- Mandatory disclaimers
- Study type hierarchy enforcement
- No dosing/treatment recommendations
- Human checkpoint always required
- Peer-reviewed source preference

### Bias Propagation

**Mitigations:**
- Diverse source requirements
- Funding source disclosure
- Devil's Advocate challenges
- Explicit uncertainty acknowledgment

---

## 10. Future Roadmap

### v0.2: Extended Domains
- Financial research adapter
- Legal research adapter
- Patent analysis adapter

### v0.3: Continuous Monitoring
- Saved queries with update alerts
- Competitive intelligence tracking
- Research landscape changes

### v0.4: Collaboration
- Multi-user research projects
- Shared finding libraries
- Expert review integration

### v1.0: Enterprise
- On-premise deployment
- Custom source integration
- Audit logging
- SSO/RBAC

---

## Appendix A: API Integrations

| Service | Purpose | Cost | Priority |
|---------|---------|------|----------|
| Tavily | Web search | $0.01/search | P0 |
| Semantic Scholar | Academic papers | Free tier | P0 |
| arXiv API | ML preprints | Free | P0 |
| PubMed API | Health research | Free | P0 |
| ClinicalTrials.gov | Trial data | Free | P1 |
| GitHub API | Code/repos | Free tier | P1 |
| Crunchbase | Company data | $$ | P2 |
| Patents API | IP research | Varies | P2 |

---

## Appendix B: Prompt Library

[To be developed during implementation - collection of tested prompts for each agent role]

---

*Document version: 0.1*
*Last updated: January 2026*
*Ready for implementation review*
