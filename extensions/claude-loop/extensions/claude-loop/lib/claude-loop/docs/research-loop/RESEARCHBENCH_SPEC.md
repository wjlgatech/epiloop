# ResearchBench: A Comprehensive Benchmark for Evaluating Research Agents

**Version 0.1 Draft**
**January 2026**

---

## Abstract

Research agents represent a rapidly emerging class of AI systems designed to autonomously gather, synthesize, and analyze information across diverse domains. Despite significant investment in this space, no comprehensive benchmark exists to evaluate these systems rigorously. We introduce **ResearchBench**, the first systematic benchmark for evaluating research agent capabilities across seven critical dimensions: question decomposition, source coverage, citation accuracy, synthesis coherence, gap identification, counterargument discovery, and confidence calibration. ResearchBench provides standardized evaluation protocols, expert-annotated ground truth, and a public leaderboard to drive progress in research automation. This specification defines the benchmark's structure, evaluation methodology, and roadmap toward a 2,000-question dataset spanning AI/ML, investment research, and general knowledge domains.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Evaluation Dimensions](#2-evaluation-dimensions)
3. [Dataset Specification](#3-dataset-specification)
4. [Ground Truth Generation](#4-ground-truth-generation)
5. [Evaluation Protocol](#5-evaluation-protocol)
6. [Submission Format](#6-submission-format)
7. [Leaderboard Design](#7-leaderboard-design)
8. [Comparison to Existing Benchmarks](#8-comparison-to-existing-benchmarks)
9. [Timeline](#9-timeline)
10. [Sample Questions](#10-sample-questions)
11. [Appendix A: Detailed Scoring Rubrics](#appendix-a-detailed-scoring-rubrics)
12. [Appendix B: API Schema](#appendix-b-api-schema)
13. [References](#references)

---

## 1. Executive Summary

### 1.1 What is ResearchBench?

ResearchBench is a comprehensive evaluation framework designed to assess the capabilities of autonomous research agents. Unlike existing benchmarks that focus on narrow tasks such as fact verification or question answering, ResearchBench evaluates the full research workflow: from understanding complex queries, through information gathering and synthesis, to uncertainty quantification and critical analysis.

The benchmark consists of:
- **A curated dataset** of 500 research questions (v0.1), expanding to 2,000 questions (v1.0)
- **Expert-annotated ground truth** including source lists, synthesis examples, and identified gaps
- **Seven evaluation dimensions** capturing distinct research competencies
- **Standardized evaluation protocols** combining automated metrics and human assessment
- **A public leaderboard** with anti-gaming measures for fair comparison

### 1.2 Why ResearchBench Matters

The development of research agents has accelerated dramatically, with systems like Perplexity, Google's Deep Research, and numerous startup offerings entering the market. However, the field lacks:

1. **Standardized evaluation criteria**: Current assessments rely on cherry-picked examples or narrow metrics that fail to capture research quality holistically.

2. **Reproducible benchmarks**: Without standardized test sets and evaluation protocols, comparing systems is impossible.

3. **Comprehensive coverage**: Existing benchmarks address fragments of research (e.g., fact-checking) but not the integrated workflow.

4. **Domain-specific evaluation**: Research quality varies significantly across domains; a single metric cannot capture this variation.

ResearchBench addresses these gaps by providing the first comprehensive, reproducible, and domain-aware benchmark for research agents.

### 1.3 Target Users

| User Category | Primary Use Case |
|--------------|------------------|
| **Academic Researchers** | Evaluate novel architectures, publish comparative studies, identify capability gaps |
| **Industry Practitioners** | Benchmark internal systems, guide procurement decisions, track improvement over time |
| **Research Agent Developers** | Identify weaknesses, guide development priorities, demonstrate competitive advantage |
| **Enterprise Evaluators** | Assess vendor claims, establish procurement criteria, validate deployments |
| **Funding Bodies & Investors** | Evaluate research agent startups, track field progress, identify promising approaches |

---

## 2. Evaluation Dimensions

ResearchBench evaluates research agents across seven orthogonal dimensions, each capturing a distinct competency required for high-quality research.

### 2.1 Dimension Overview

| Dimension | What It Measures | Metric | Range | Weight |
|-----------|-----------------|--------|-------|--------|
| **Question Decomposition** | Quality of breaking complex questions into sub-questions | Expert Rating | 0-100 | 15% |
| **Source Coverage** | Did the agent find all relevant sources? | Recall vs Expert List | 0.0-1.0 | 20% |
| **Citation Accuracy** | Are citations real and correctly attributed? | Precision | 0.0-1.0 | 15% |
| **Synthesis Coherence** | Is the synthesis accurate and well-organized? | Human Rating | 1-5 | 20% |
| **Gap Identification** | Did the agent identify missing information? | F1 vs Expert Gaps | 0.0-1.0 | 10% |
| **Counterargument Discovery** | Did the agent find opposing viewpoints? | Recall | 0.0-1.0 | 10% |
| **Confidence Calibration** | Does stated confidence match actual accuracy? | ECE | 0.0-1.0 (lower=better) | 10% |

### 2.2 Detailed Dimension Specifications

#### 2.2.1 Question Decomposition (QD)

**Definition**: The ability to analyze a complex research question and decompose it into logical, comprehensive, and appropriately scoped sub-questions.

**Evaluation Criteria**:
- **Completeness** (0-25): Do sub-questions cover all aspects of the original query?
- **Logical Structure** (0-25): Are sub-questions organized in a coherent hierarchy?
- **Appropriate Granularity** (0-25): Are sub-questions neither too broad nor too narrow?
- **Independence** (0-25): Do sub-questions minimize redundancy while maintaining coverage?

**Scoring Process**:
1. Expert annotators independently score each criterion
2. Final score = mean of four criteria scores
3. Inter-rater reliability checked via Cohen's kappa (required: κ > 0.7)

**Example**:
```
Original Question: "What are the implications of transformer architecture
                   scaling laws for AGI timelines?"

High-Quality Decomposition (Score: 85):
1. What are the established scaling laws for transformer models?
   1.1. Compute scaling relationships (Chinchilla, GPT-4 trends)
   1.2. Data scaling relationships
   1.3. Parameter count relationships
2. What capabilities emerge at different scales?
   2.1. Documented emergent abilities
   2.2. Capability thresholds and phase transitions
3. What are current AGI timeline estimates from credible sources?
4. How do scaling projections intersect with AGI requirements?
5. What are the main critiques of scaling-based AGI predictions?

Low-Quality Decomposition (Score: 30):
1. What are transformers?
2. What is AGI?
3. When will we get AGI?
```

#### 2.2.2 Source Coverage (SC)

**Definition**: The proportion of relevant, authoritative sources identified by the agent relative to an expert-curated reference list.

**Metric**: Recall@K where K = |expert source list|

$$\text{Source Coverage} = \frac{|\text{Agent Sources} \cap \text{Expert Sources}|}{|\text{Expert Sources}|}$$

**Source Matching Criteria**:
- Exact URL match: Full credit
- Same document, different URL: Full credit (canonicalization applied)
- Same primary finding from different source: Partial credit (0.5)
- Derivative/secondary source citing primary: Partial credit (0.3)

**Expert Source List Construction**:
- Minimum 3 domain experts per question
- Sources categorized by importance (essential, important, supplementary)
- Weighted recall computed: essential sources count 2x, important 1x, supplementary 0.5x

**Evaluation Notes**:
- Time-sensitivity handled via source publication date requirements
- Domain-specific source hierarchies (e.g., peer-reviewed > preprint > blog)
- Duplicate sources from agent consolidated before scoring

#### 2.2.3 Citation Accuracy (CA)

**Definition**: The precision of citations provided by the agent, measuring both existence and attribution correctness.

**Metric**: Citation Precision

$$\text{Citation Accuracy} = \frac{\text{Correct Citations}}{\text{Total Citations}}$$

**Citation Verification Process**:
1. **Existence Check**: Does the cited source exist?
   - URL verification (with archival fallback)
   - DOI resolution
   - Title/author search verification
2. **Attribution Check**: Does the source actually contain the claimed information?
   - Exact quote verification
   - Paraphrase accuracy assessment
   - Numerical/statistical claim verification
3. **Context Check**: Is the citation used appropriately?
   - Not taken out of context
   - Not misrepresenting author's position
   - Appropriate for the claim being supported

**Scoring**:
- Exists + Accurate + Appropriate Context: 1.0
- Exists + Accurate + Minor Context Issues: 0.8
- Exists + Partially Accurate: 0.5
- Exists but Inaccurate: 0.2
- Does Not Exist (hallucinated): 0.0

#### 2.2.4 Synthesis Coherence (SYN)

**Definition**: The quality of the agent's synthesis, encompassing accuracy, organization, clarity, and insight.

**Metric**: Human Rating (1-5 scale)

**Evaluation Rubric**:

| Score | Description |
|-------|-------------|
| **5 - Excellent** | Synthesis is accurate, comprehensive, well-organized, and provides genuine insight. Could be published with minor editing. |
| **4 - Good** | Synthesis is accurate and well-organized with minor gaps or clarity issues. Useful for professional purposes. |
| **3 - Adequate** | Synthesis captures main points but has organizational issues, minor inaccuracies, or lacks depth. Requires significant editing. |
| **2 - Poor** | Synthesis has substantial inaccuracies, poor organization, or significant gaps. Limited utility without major revision. |
| **1 - Unacceptable** | Synthesis is largely inaccurate, incoherent, or fails to address the research question. |

**Sub-criteria** (each rated 1-5, averaged):
- Factual Accuracy
- Logical Organization
- Appropriate Depth
- Clarity of Expression
- Integration of Sources

#### 2.2.5 Gap Identification (GI)

**Definition**: The ability to identify limitations, missing information, and areas where current evidence is insufficient.

**Metric**: F1 Score vs Expert Gap List

$$\text{Gap F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

**Gap Categories**:
1. **Data Gaps**: Missing empirical data or studies
2. **Temporal Gaps**: Outdated information requiring updates
3. **Methodological Gaps**: Limitations in study designs
4. **Scope Gaps**: Areas not covered by available literature
5. **Consensus Gaps**: Areas of active debate without resolution

**Matching Criteria**:
- Exact match: 1.0
- Semantically equivalent gap: 0.8
- Related but distinct gap: 0.3
- Unrelated gap: 0.0

#### 2.2.6 Counterargument Discovery (CD)

**Definition**: The ability to identify and present opposing viewpoints, critiques, and alternative perspectives.

**Metric**: Recall vs Expert Counterargument List

$$\text{Counterargument Recall} = \frac{|\text{Agent Counterargs} \cap \text{Expert Counterargs}|}{|\text{Expert Counterargs}|}$$

**Counterargument Categories**:
1. **Methodological Critiques**: Challenges to study designs or data quality
2. **Alternative Interpretations**: Different explanations for the same evidence
3. **Opposing Positions**: Direct disagreement with conclusions
4. **Boundary Conditions**: Cases where findings may not apply
5. **Unaddressed Concerns**: Issues raised by credible critics

**Quality Adjustment**:
- Well-explained counterargument: 1.0
- Mentioned but not explained: 0.5
- Strawman version: 0.2

#### 2.2.7 Confidence Calibration (CC)

**Definition**: The alignment between the agent's stated confidence levels and the actual accuracy of its claims.

**Metric**: Expected Calibration Error (ECE)

$$\text{ECE} = \sum_{b=1}^{B} \frac{n_b}{N} |\text{acc}(b) - \text{conf}(b)|$$

Where:
- B = number of confidence bins (typically 10)
- n_b = number of claims in bin b
- acc(b) = accuracy of claims in bin b
- conf(b) = average confidence in bin b

**Confidence Extraction**:
- Explicit confidence statements parsed
- Hedging language mapped to confidence levels:
  - "Definitely", "Certainly" → 0.95
  - "Likely", "Probably" → 0.75
  - "Possibly", "May" → 0.50
  - "Unlikely", "Doubtful" → 0.25
  - "Almost certainly not" → 0.05

**Interpretation**:
- ECE = 0.0: Perfect calibration
- ECE < 0.1: Well calibrated
- ECE 0.1-0.2: Moderately calibrated
- ECE > 0.2: Poorly calibrated

---

## 3. Dataset Specification

### 3.1 Domain Distribution

ResearchBench covers three primary domains with distinct research characteristics:

| Domain | Percentage | Rationale | Example Topics |
|--------|-----------|-----------|----------------|
| **AI/ML Research** | 40% | High activity, rapid change, technical depth | Scaling laws, architectures, safety |
| **Investment Research** | 30% | High stakes, requires synthesis, time-sensitive | Market analysis, company research |
| **General Knowledge** | 30% | Breadth, accessibility, diverse sources | Science, policy, history |

#### 3.1.1 AI/ML Research (200 questions v0.1 / 800 questions v1.0)

**Subcategories**:
- Model Architectures & Training (25%)
- Capabilities & Benchmarks (20%)
- Safety & Alignment (20%)
- Applications & Deployment (15%)
- Industry & Market (10%)
- Research Methodology (10%)

**Characteristic Challenges**:
- Rapid publication cycle (arXiv preprints)
- Technical jargon and mathematical content
- Frequent terminology shifts
- Reproducibility verification

#### 3.1.2 Investment Research (150 questions v0.1 / 600 questions v1.0)

**Subcategories**:
- Public Company Analysis (30%)
- Industry/Sector Research (25%)
- Macroeconomic Analysis (20%)
- Emerging Technology Assessment (15%)
- Risk Analysis (10%)

**Characteristic Challenges**:
- Time-sensitivity of information
- Conflicting analyst opinions
- Regulatory filings interpretation
- Forward-looking uncertainty

#### 3.1.3 General Knowledge (150 questions v0.1 / 600 questions v1.0)

**Subcategories**:
- Scientific Research (30%)
- Policy & Governance (25%)
- Historical Analysis (20%)
- Health & Medicine (15%)
- Environmental Issues (10%)

**Characteristic Challenges**:
- Source credibility variation
- Politically contested topics
- Interdisciplinary synthesis
- Accessibility vs. depth tradeoffs

### 3.2 Question Types

| Type | Percentage | Description | Example |
|------|-----------|-------------|---------|
| **Factual** | 25% | Questions with objective, verifiable answers | "What was NVIDIA's R&D spending in 2024?" |
| **Analytical** | 35% | Questions requiring interpretation and analysis | "What factors explain Tesla's delivery growth slowdown?" |
| **Comparative** | 25% | Questions requiring multi-entity comparison | "How do RAG approaches compare to fine-tuning for domain adaptation?" |
| **Predictive** | 15% | Questions about future trends or outcomes | "What are the likely impacts of EU AI Act on foundation model deployment?" |

### 3.3 Difficulty Levels

| Level | Percentage | Criteria | Expected Time |
|-------|-----------|----------|---------------|
| **Easy** | 30% | Single domain, well-documented topic, few sources needed | 15-30 min |
| **Medium** | 45% | Cross-domain synthesis, moderate source diversity, some ambiguity | 30-60 min |
| **Hard** | 25% | Multi-domain, conflicting sources, requires expert judgment, significant ambiguity | 60-120 min |

**Difficulty Calibration**:
- Each question piloted with 3+ human researchers
- Difficulty adjusted based on:
  - Time to answer
  - Source diversity required
  - Inter-researcher agreement
  - Synthesis complexity

### 3.4 Question Quality Criteria

All questions must meet the following criteria:

1. **Answerability**: Can be answered with publicly available information
2. **Scope**: Neither trivially simple nor impossibly broad
3. **Objectivity**: Has objectively assessable answer quality
4. **Recency**: Does not require real-time information (>24h old acceptable)
5. **Non-Ephemeral**: Answer not expected to change within evaluation period
6. **Ethical**: Does not require or encourage harmful research activities
7. **Diversity**: Does not duplicate existing questions in substance

---

## 4. Ground Truth Generation

### 4.1 Expert Annotation Process

#### 4.1.1 Annotator Qualification

**Domain Expert Requirements**:
- AI/ML: PhD or 5+ years industry experience in ML/AI
- Investment: CFA charter or 5+ years professional research experience
- General: Advanced degree in relevant field or demonstrated expertise

**Training Protocol**:
1. 2-hour benchmark orientation session
2. 10 practice questions with feedback
3. Calibration exercise (must achieve κ > 0.7 with gold standard)
4. Ongoing quality monitoring (random re-annotation of 10%)

#### 4.1.2 Annotation Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GROUND TRUTH GENERATION                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │Question │───▶│  Expert 1   │───▶│  Expert 2   │───▶│  Expert 3   │  │
│  │ Input   │    │ Annotation  │    │ Annotation  │    │ Annotation  │  │
│  └─────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                        │                 │                  │          │
│                        ▼                 ▼                  ▼          │
│                 ┌─────────────────────────────────────────────┐        │
│                 │           Agreement Check (κ > 0.8)         │        │
│                 └─────────────────────────────────────────────┘        │
│                        │                                               │
│              ┌─────────┴─────────┐                                     │
│              ▼                   ▼                                     │
│     ┌─────────────┐      ┌─────────────┐                               │
│     │  κ ≥ 0.8    │      │  κ < 0.8    │                               │
│     │  Merge &    │      │ Adjudication│                               │
│     │  Finalize   │      │  Required   │                               │
│     └─────────────┘      └─────────────┘                               │
│              │                   │                                     │
│              ▼                   ▼                                     │
│     ┌─────────────┐      ┌─────────────┐                               │
│     │   Final     │      │  Expert 4   │                               │
│     │  Ground     │◀─────│Adjudicator  │                               │
│     │   Truth     │      │  Resolves   │                               │
│     └─────────────┘      └─────────────┘                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.3 Annotation Deliverables

For each question, experts produce:

1. **Reference Decomposition**: Optimal sub-question breakdown
2. **Source List**: Categorized as Essential (E), Important (I), or Supplementary (S)
3. **Reference Synthesis**: Expert-written synthesis (gold standard)
4. **Gap List**: Identified information gaps with categories
5. **Counterargument List**: Known opposing views with explanations
6. **Confidence Anchors**: Key claims with verified accuracy for calibration

### 4.2 Inter-Annotator Agreement Requirements

| Dimension | Agreement Metric | Threshold | Resolution Process |
|-----------|-----------------|-----------|-------------------|
| Question Decomposition | Cohen's κ | > 0.70 | Adjudicator review |
| Source List | Jaccard Index | > 0.60 | Union with categorization |
| Citation Accuracy | Exact Agreement | > 0.90 | Verification protocol |
| Synthesis Quality | Krippendorff's α | > 0.75 | Discussion + re-rating |
| Gap Identification | Cohen's κ | > 0.65 | Adjudicator merge |
| Counterarguments | Cohen's κ | > 0.65 | Union approach |

### 4.3 Source List Curation Methodology

#### 4.3.1 Source Discovery Protocol

1. **Expert Independent Search**: Each expert independently identifies sources
2. **Source Pool Merge**: All sources combined into candidate pool
3. **Relevance Rating**: Each expert rates all sources (0-3 relevance)
4. **Categorization**: Sources with mean rating > 2.0 categorized as E/I/S
5. **Verification**: All included sources verified for accessibility

#### 4.3.2 Source Metadata

Each source in ground truth includes:
```json
{
  "url": "https://arxiv.org/abs/2203.15556",
  "title": "Training Compute-Optimal Large Language Models",
  "authors": ["Hoffmann et al."],
  "publication_date": "2022-03-29",
  "source_type": "preprint",
  "importance": "essential",
  "relevant_sections": ["Section 3", "Figure 2"],
  "key_claims": ["Chinchilla scaling laws", "Compute-optimal ratio"],
  "last_verified": "2026-01-15"
}
```

---

## 5. Evaluation Protocol

### 5.1 Automated Metrics

#### 5.1.1 Citation Verification Pipeline

```python
class CitationVerifier:
    """Automated citation verification system."""

    def verify_citation(self, citation: Citation) -> VerificationResult:
        # Step 1: URL/DOI Resolution
        exists = self.check_existence(citation.url)
        if not exists:
            exists = self.archive_fallback(citation.url)

        # Step 2: Content Retrieval
        if exists:
            content = self.retrieve_content(citation.url)

            # Step 3: Claim Verification
            claim_score = self.verify_claim(
                claim=citation.claim,
                source_content=content,
                quoted_text=citation.quote
            )

            # Step 4: Context Appropriateness
            context_score = self.assess_context(
                claim=citation.claim,
                source_content=content,
                usage_context=citation.context
            )

            return VerificationResult(
                exists=True,
                claim_accuracy=claim_score,
                context_appropriateness=context_score,
                overall_score=self.compute_overall(exists, claim_score, context_score)
            )

        return VerificationResult(exists=False, overall_score=0.0)
```

#### 5.1.2 Source Coverage Computation

```python
def compute_source_coverage(
    agent_sources: List[Source],
    expert_sources: List[Source]
) -> float:
    """Compute weighted source coverage recall."""

    # Canonicalize URLs
    agent_canonical = {canonicalize(s.url) for s in agent_sources}

    weighted_hits = 0.0
    weighted_total = 0.0

    for expert_source in expert_sources:
        # Weight by importance
        weight = {
            "essential": 2.0,
            "important": 1.0,
            "supplementary": 0.5
        }[expert_source.importance]

        weighted_total += weight

        # Check for match
        expert_canonical = canonicalize(expert_source.url)

        if expert_canonical in agent_canonical:
            weighted_hits += weight
        elif has_equivalent_finding(agent_sources, expert_source):
            weighted_hits += weight * 0.5  # Partial credit

    return weighted_hits / weighted_total if weighted_total > 0 else 0.0
```

#### 5.1.3 Confidence Calibration (ECE Computation)

```python
def compute_ece(
    claims: List[Claim],
    num_bins: int = 10
) -> float:
    """Compute Expected Calibration Error."""

    # Extract confidence and accuracy for each claim
    confidences = [extract_confidence(c.text) for c in claims]
    accuracies = [verify_accuracy(c) for c in claims]

    # Bin claims by confidence
    bins = [[] for _ in range(num_bins)]
    for conf, acc in zip(confidences, accuracies):
        bin_idx = min(int(conf * num_bins), num_bins - 1)
        bins[bin_idx].append((conf, acc))

    # Compute ECE
    ece = 0.0
    n_total = len(claims)

    for bin_claims in bins:
        if len(bin_claims) == 0:
            continue

        bin_conf = np.mean([c[0] for c in bin_claims])
        bin_acc = np.mean([c[1] for c in bin_claims])
        bin_weight = len(bin_claims) / n_total

        ece += bin_weight * abs(bin_acc - bin_conf)

    return ece
```

### 5.2 Human Evaluation Protocol

#### 5.2.1 Evaluator Selection

- Domain expertise required for domain-specific questions
- Training on rubric with calibration exercises
- Blind evaluation (evaluator does not know which system produced output)
- No self-evaluation (evaluators cannot rate systems they developed)

#### 5.2.2 Evaluation Interface

Evaluators assess submissions through a standardized interface:

1. **Question Display**: Full research question with context
2. **Reference Materials**: Expert decomposition, source list, synthesis (available on request)
3. **Agent Submission**: Full output including decomposition, sources, synthesis
4. **Rating Interface**: Dimension-specific rubrics with examples
5. **Justification**: Free-text explanation required for extreme scores (1 or 5)

#### 5.2.3 Quality Control

- 10% of evaluations are duplicate assignments (hidden)
- Evaluators with < 0.7 agreement on duplicates flagged for review
- Monthly calibration sessions maintain consistency
- Evaluation time logged; outliers reviewed

### 5.3 Scoring Aggregation

#### 5.3.1 Per-Question Score

$$\text{Score}_q = \sum_{d \in \text{Dimensions}} w_d \times \text{normalize}_d(\text{raw}_d)$$

Where:
- $w_d$ = dimension weight (see Section 2.1)
- $\text{normalize}_d$ = dimension-specific normalization to [0, 1]
- $\text{raw}_d$ = raw dimension score

#### 5.3.2 Normalization Functions

| Dimension | Normalization |
|-----------|---------------|
| Question Decomposition | raw / 100 |
| Source Coverage | raw (already 0-1) |
| Citation Accuracy | raw (already 0-1) |
| Synthesis Coherence | (raw - 1) / 4 |
| Gap Identification | raw (already 0-1) |
| Counterargument Discovery | raw (already 0-1) |
| Confidence Calibration | 1 - raw (invert ECE) |

#### 5.3.3 Aggregate Scores

**Overall Score**:
$$\text{Overall} = \frac{1}{|Q|} \sum_{q \in Q} \text{Score}_q$$

**Domain Scores**: Computed separately for AI/ML, Investment, General

**Difficulty Scores**: Computed separately for Easy, Medium, Hard

---

## 6. Submission Format

### 6.1 API Specification

Submissions are made via a standardized JSON API.

#### 6.1.1 Submission Endpoint

```
POST https://api.researchbench.org/v1/submissions
Authorization: Bearer <api_key>
Content-Type: application/json
```

#### 6.1.2 Request Schema

```json
{
  "submission_id": "string (UUID)",
  "system_name": "string",
  "system_version": "string",
  "timestamp": "ISO 8601 datetime",
  "questions": [
    {
      "question_id": "string",
      "response": {
        "decomposition": {
          "sub_questions": [
            {
              "id": "string",
              "text": "string",
              "parent_id": "string | null",
              "rationale": "string"
            }
          ]
        },
        "sources": [
          {
            "url": "string",
            "title": "string",
            "accessed_date": "ISO 8601 date",
            "relevance_explanation": "string"
          }
        ],
        "synthesis": {
          "content": "string (markdown)",
          "structure": [
            {
              "section": "string",
              "content": "string"
            }
          ]
        },
        "citations": [
          {
            "claim": "string",
            "source_url": "string",
            "quote": "string | null",
            "location": "string"
          }
        ],
        "gaps": [
          {
            "description": "string",
            "category": "data | temporal | methodological | scope | consensus",
            "importance": "high | medium | low"
          }
        ],
        "counterarguments": [
          {
            "position": "string",
            "source_url": "string | null",
            "explanation": "string"
          }
        ],
        "confidence_statements": [
          {
            "claim": "string",
            "confidence": "number (0-1)",
            "justification": "string"
          }
        ],
        "metadata": {
          "processing_time_seconds": "number",
          "sources_consulted": "number",
          "model_calls": "number"
        }
      }
    }
  ]
}
```

### 6.2 Required Output Fields

| Field | Required | Description |
|-------|----------|-------------|
| `decomposition` | Yes | Sub-question breakdown |
| `sources` | Yes | List of consulted sources |
| `synthesis` | Yes | Main research output |
| `citations` | Yes | Inline citation details |
| `gaps` | Yes | Identified information gaps |
| `counterarguments` | Yes | Opposing viewpoints found |
| `confidence_statements` | Yes | Confidence levels for key claims |
| `metadata` | No | Processing statistics |

### 6.3 Example Submission

```json
{
  "submission_id": "550e8400-e29b-41d4-a716-446655440000",
  "system_name": "ResearchBot-Pro",
  "system_version": "2.1.0",
  "timestamp": "2026-01-15T14:30:00Z",
  "questions": [
    {
      "question_id": "aiml-042",
      "response": {
        "decomposition": {
          "sub_questions": [
            {
              "id": "sq-1",
              "text": "What are the current state-of-the-art approaches to RLHF?",
              "parent_id": null,
              "rationale": "Establishes baseline understanding of current methods"
            },
            {
              "id": "sq-2",
              "text": "What are the documented failure modes of RLHF?",
              "parent_id": null,
              "rationale": "Identifies known limitations"
            },
            {
              "id": "sq-2a",
              "text": "What is reward hacking and when does it occur?",
              "parent_id": "sq-2",
              "rationale": "Specific failure mode requiring detailed analysis"
            }
          ]
        },
        "sources": [
          {
            "url": "https://arxiv.org/abs/2204.05862",
            "title": "Training language models to follow instructions with human feedback",
            "accessed_date": "2026-01-14",
            "relevance_explanation": "Foundational InstructGPT paper establishing RLHF methodology"
          }
        ],
        "synthesis": {
          "content": "## Overview\n\nRLHF (Reinforcement Learning from Human Feedback) has become...",
          "structure": [
            {
              "section": "Overview",
              "content": "RLHF has become the dominant approach..."
            },
            {
              "section": "Current Approaches",
              "content": "The standard RLHF pipeline consists of..."
            }
          ]
        },
        "citations": [
          {
            "claim": "InstructGPT demonstrated that RLHF could significantly improve helpfulness and reduce harmful outputs",
            "source_url": "https://arxiv.org/abs/2204.05862",
            "quote": "We find that InstructGPT models show improvements in truthfulness and reductions in toxic output generation",
            "location": "Abstract"
          }
        ],
        "gaps": [
          {
            "description": "Limited published research on RLHF performance at very large scales (>1T parameters)",
            "category": "data",
            "importance": "high"
          }
        ],
        "counterarguments": [
          {
            "position": "Some researchers argue that RLHF primarily teaches models to appear helpful rather than be genuinely helpful",
            "source_url": "https://arxiv.org/abs/2310.xxxxx",
            "explanation": "This critique suggests RLHF optimizes for human approval signals rather than actual task completion quality"
          }
        ],
        "confidence_statements": [
          {
            "claim": "RLHF is currently the most widely used alignment technique in production LLMs",
            "confidence": 0.95,
            "justification": "Multiple public statements from major labs confirm RLHF usage"
          }
        ],
        "metadata": {
          "processing_time_seconds": 145,
          "sources_consulted": 23,
          "model_calls": 8
        }
      }
    }
  ]
}
```

---

## 7. Leaderboard Design

### 7.1 Public vs Private Test Sets

| Set | Size (v0.1) | Size (v1.0) | Purpose |
|-----|-------------|-------------|---------|
| **Public Dev** | 50 | 200 | Development, debugging, public examples |
| **Public Test** | 150 | 600 | Official public benchmark results |
| **Private Test** | 300 | 1200 | Hidden evaluation, anti-gaming |

**Private Test Set Properties**:
- Questions never publicly released
- Results computed server-side only
- Used for final leaderboard rankings
- Rotated quarterly (25% replacement)

### 7.2 Anti-Gaming Measures

#### 7.2.1 Hidden Question Pool

- Private test set contains 2x questions needed for evaluation
- Each submission evaluated on random 50% subset
- Subset selection seeded by submission hash (reproducible but unpredictable)

#### 7.2.2 Temporal Diversity

- Questions span multiple time periods
- Some questions have time-specific correct answers
- Prevents memorization of static answer sets

#### 7.2.3 Paraphrase Variants

- Each question has 3-5 paraphrase variants
- Variants used randomly in evaluation
- Tests robustness to query reformulation

#### 7.2.4 Submission Limits

| Submission Type | Limit | Reset Period |
|-----------------|-------|--------------|
| Public Dev | Unlimited | N/A |
| Public Test | 10/month | Monthly |
| Private Test | 3/month | Monthly |

#### 7.2.5 Output Verification

- Random manual review of 5% of submissions
- Automated detection of memorized outputs
- Pattern matching against training data leakage

### 7.3 Leaderboard Categories

#### 7.3.1 Main Leaderboard

| Rank | System | Overall | QD | SC | CA | SYN | GI | CD | CC |
|------|--------|---------|----|----|----|----|----|----|-----|
| 1 | System A | 0.847 | 82 | 0.91 | 0.94 | 4.2 | 0.78 | 0.82 | 0.08 |
| 2 | System B | 0.823 | 79 | 0.88 | 0.92 | 4.0 | 0.75 | 0.79 | 0.11 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

#### 7.3.2 Domain Leaderboards

- AI/ML Research
- Investment Research
- General Knowledge

#### 7.3.3 Difficulty Leaderboards

- Easy Questions
- Medium Questions
- Hard Questions

#### 7.3.4 Efficiency Track

Optional track measuring performance per compute:
- Score / API calls
- Score / processing time
- Score / estimated cost

### 7.4 Submission Metadata Requirements

Each submission must include:

```json
{
  "system_info": {
    "name": "string",
    "version": "string",
    "organization": "string",
    "is_commercial": "boolean",
    "paper_url": "string | null",
    "code_url": "string | null"
  },
  "compute_info": {
    "estimated_cost_per_question_usd": "number",
    "average_latency_seconds": "number",
    "infrastructure": "string"
  }
}
```

---

## 8. Comparison to Existing Benchmarks

### 8.1 Benchmark Landscape

| Benchmark | Domain | Task Type | Research Relevance |
|-----------|--------|-----------|-------------------|
| **SWE-bench** | Software | Code generation/repair | Low - coding only |
| **AgentBench** | General | Multi-task agents | Medium - some research tasks |
| **FEVER** | Facts | Claim verification | Medium - verification only |
| **HotpotQA** | General | Multi-hop QA | Medium - reasoning only |
| **QASPER** | Science | Paper QA | Medium - single-paper scope |
| **ResearchBench** | Research | Full research workflow | **High - comprehensive** |

### 8.2 Detailed Comparisons

#### 8.2.1 vs SWE-bench

**SWE-bench** evaluates coding agents on real GitHub issues.

| Aspect | SWE-bench | ResearchBench |
|--------|-----------|---------------|
| **Domain** | Software engineering | Cross-domain research |
| **Task** | Bug fixing, feature implementation | Information synthesis |
| **Evaluation** | Test suite pass/fail | Multi-dimensional assessment |
| **Ground Truth** | Existing patches | Expert annotations |
| **Skills Tested** | Coding, debugging | Analysis, synthesis, judgment |

**Why ResearchBench is Needed**: SWE-bench excels at evaluating coding capabilities but does not assess research skills like source evaluation, synthesis quality, or uncertainty quantification.

#### 8.2.2 vs AgentBench

**AgentBench** evaluates LLM agents across diverse environments.

| Aspect | AgentBench | ResearchBench |
|--------|------------|---------------|
| **Scope** | 8 environments (OS, DB, web, etc.) | Research workflow |
| **Depth** | Breadth-focused | Depth in research domain |
| **Metrics** | Task completion | 7-dimensional quality |
| **Real-world Alignment** | Mixed | High for research use cases |

**Why ResearchBench is Needed**: AgentBench provides breadth but lacks depth in research evaluation. It includes some web-based tasks but does not assess synthesis quality, citation accuracy, or critical thinking.

#### 8.2.3 vs FEVER

**FEVER** (Fact Extraction and VERification) evaluates claim verification.

| Aspect | FEVER | ResearchBench |
|--------|-------|---------------|
| **Task** | Binary claim verification | Full research workflow |
| **Scope** | Single claims | Complex questions |
| **Sources** | Wikipedia only | Open web + databases |
| **Output** | Supported/Refuted/NEI | Comprehensive synthesis |

**Why ResearchBench is Needed**: FEVER addresses only the verification component of research. Real research requires synthesis, gap identification, and nuanced confidence assessment beyond binary classification.

#### 8.2.4 vs HotpotQA

**HotpotQA** evaluates multi-hop reasoning over Wikipedia.

| Aspect | HotpotQA | ResearchBench |
|--------|----------|---------------|
| **Reasoning** | 2-hop | Unlimited complexity |
| **Sources** | Wikipedia paragraphs | Open web |
| **Output** | Short answers | Extended synthesis |
| **Evaluation** | Exact match | Multi-dimensional |

**Why ResearchBench is Needed**: HotpotQA tests reasoning ability but constrains source access and output format. Research agents need to handle open-ended source discovery and produce comprehensive outputs.

### 8.3 Gap Analysis

ResearchBench uniquely addresses:

1. **End-to-End Workflow**: No existing benchmark evaluates the complete research pipeline
2. **Source Quality Assessment**: Other benchmarks assume sources are given or correct
3. **Synthesis Evaluation**: Most benchmarks use extractive or short-form answers
4. **Uncertainty Quantification**: Confidence calibration rarely assessed
5. **Critical Analysis**: Gap identification and counterarguments not measured elsewhere
6. **Domain Diversity**: Research spans domains with different evaluation criteria

---

## 9. Timeline

### 9.1 Development Roadmap

```
2025 Q4                    2026 Q1                    2026 Q2                    2026 Q3-Q4
    │                          │                          │                          │
    ▼                          ▼                          ▼                          ▼
┌─────────┐              ┌─────────┐              ┌─────────┐              ┌─────────┐
│ Design  │              │  v0.1   │              │ Public  │              │  v1.0   │
│  Phase  │─────────────▶│ Release │─────────────▶│  Beta   │─────────────▶│ Release │
└─────────┘              └─────────┘              └─────────┘              └─────────┘
                              │                        │                        │
                              │                        │                        │
    Specification         500 questions            Leaderboard            2000 questions
    Annotation protocol   Basic evaluation         Competition            Full evaluation
    Pilot testing         API launch               Community feedback     Paper submission
```

### 9.2 Milestone Details

#### Phase 1: Design (2025 Q4) - COMPLETE

- [x] Evaluation dimension specification
- [x] Annotation protocol design
- [x] Question type taxonomy
- [x] API schema definition
- [x] Pilot annotation (50 questions)

#### Phase 2: v0.1 Release (2026 Q1)

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Question Generation | Jan 31, 2026 | 600 candidate questions |
| Expert Annotation | Feb 28, 2026 | 500 questions with ground truth |
| Evaluation Pipeline | Mar 15, 2026 | Automated + human eval system |
| API Launch | Mar 31, 2026 | Public submission API |

#### Phase 3: Public Beta (2026 Q2)

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Leaderboard Launch | Apr 15, 2026 | Public leaderboard site |
| Competition | May 1 - Jun 15, 2026 | Open competition track |
| Feedback Integration | Jun 30, 2026 | v0.2 with improvements |

#### Phase 4: v1.0 Release (2026 Q3-Q4)

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Dataset Expansion | Sep 30, 2026 | 2000 questions annotated |
| Evaluation Refinement | Oct 31, 2026 | Improved metrics based on feedback |
| Paper Submission | Nov 15, 2026 | NeurIPS Datasets Track submission |
| v1.0 Launch | Dec 15, 2026 | Full benchmark release |

### 9.3 Resource Requirements

| Phase | Annotation Hours | Engineering Hours | Estimated Cost |
|-------|-----------------|-------------------|----------------|
| v0.1 | 2,000 | 500 | $150,000 |
| Beta | 500 | 300 | $50,000 |
| v1.0 | 6,000 | 800 | $400,000 |
| **Total** | **8,500** | **1,600** | **$600,000** |

---

## 10. Sample Questions

### 10.1 AI/ML Domain

#### Question AIML-001 (Easy, Factual)

**Question**: What is the context window size of GPT-4 Turbo, and how does it compare to the original GPT-4?

**Expected Output Summary**:
- GPT-4 Turbo: 128K tokens
- Original GPT-4: 8K tokens (32K variant available)
- Sources: OpenAI announcements, documentation
- Confidence: High (well-documented)

---

#### Question AIML-002 (Medium, Analytical)

**Question**: What are the primary technical approaches being used to extend context windows in large language models, and what are the tradeoffs of each approach?

**Expected Sub-questions**:
1. What are the computational constraints of standard attention?
2. What sparse attention patterns have been proposed?
3. How do retrieval-augmented approaches handle long context?
4. What are memory-based approaches to context extension?

**Expected Sources** (Essential):
- "Longformer" paper (sparse attention)
- "Big Bird" paper (random + global attention)
- Ring Attention paper
- ALiBi position encoding paper

**Expected Gaps**:
- Limited benchmarking of retrieval vs native long context
- Unclear how approaches scale beyond 1M tokens

---

#### Question AIML-003 (Hard, Predictive)

**Question**: Based on current research trajectories, what architectural innovations are most likely to succeed the transformer architecture within the next 5 years, and what evidence supports each candidate?

**Expected Analysis**:
- State Space Models (Mamba, etc.): Evidence, limitations
- Mixture of Experts scaling: Evidence, limitations
- Hybrid architectures: Evidence, limitations
- Novel attention mechanisms: Evidence, limitations

**Expected Counterarguments**:
- "Bitter lesson" suggests scaling may matter more than architecture
- Transformers may simply be extended rather than replaced
- Economic lock-in effects may slow transitions

**Confidence Calibration Expected**:
- High uncertainty appropriate (0.3-0.5 confidence)
- Clear articulation of assumptions

---

### 10.2 Investment Domain

#### Question INV-001 (Easy, Factual)

**Question**: What was NVIDIA's revenue growth rate in their data center segment for fiscal year 2024?

**Expected Output**:
- Data center revenue: ~$47.5B (FY2024)
- Growth rate: ~217% YoY
- Sources: NVIDIA 10-K, earnings calls
- Confidence: Very high (audited financials)

---

#### Question INV-002 (Medium, Comparative)

**Question**: Compare the AI chip strategies of NVIDIA, AMD, and Intel, including their current market positions, product roadmaps, and competitive advantages.

**Expected Structure**:
1. Market share analysis (current state)
2. Product portfolio comparison
3. Roadmap comparison (announced products)
4. Competitive moat analysis
5. Risk factors for each

**Expected Sources**:
- Company 10-Ks and earnings transcripts
- Industry analyst reports
- Technical product documentation
- Third-party market share data

**Expected Gaps**:
- Limited visibility into enterprise adoption rates
- Classified/proprietary performance benchmarks

---

#### Question INV-003 (Hard, Analytical)

**Question**: Analyze the investment implications of the EU AI Act for US-based AI companies with significant European revenue exposure. Which companies face the greatest regulatory risk, and what mitigation strategies are available?

**Expected Analysis**:
- EU AI Act key provisions summary
- Risk categorization framework
- Company-by-company exposure analysis
- Mitigation strategy evaluation
- Timeline considerations

**Expected Counterarguments**:
- Regulation may create barriers to entry (positive for incumbents)
- Compliance costs may be lower than expected
- Enforcement uncertainty reduces near-term impact

---

### 10.3 General Knowledge Domain

#### Question GEN-001 (Easy, Factual)

**Question**: What percentage of global electricity generation came from renewable sources in 2023, and how has this changed over the past decade?

**Expected Output**:
- 2023: ~30% of global electricity from renewables
- 2013: ~22% from renewables
- Breakdown by source type
- Regional variations
- Sources: IEA, IRENA, national statistics

---

#### Question GEN-002 (Medium, Analytical)

**Question**: What are the main scientific debates around the effectiveness of carbon capture and storage (CCS) as a climate mitigation strategy?

**Expected Sub-questions**:
1. What is the current state of CCS technology?
2. What are the scalability challenges?
3. What are the economic arguments for and against?
4. What do climate models assume about CCS deployment?

**Expected Counterarguments**:
- Moral hazard argument (delays emissions reduction)
- Energy penalty concerns
- Long-term storage security questions
- Alternative use of investment capital

---

#### Question GEN-003 (Hard, Comparative)

**Question**: Compare the pandemic preparedness frameworks of the US, EU, and China based on their COVID-19 responses. What structural changes have been implemented since 2020, and how effective are they likely to be for future pandemics?

**Expected Analysis**:
- Pre-2020 framework comparison
- COVID-19 response evaluation
- Post-pandemic reforms by region
- Gap analysis vs WHO recommendations
- Expert predictions for future preparedness

**Expected Gaps**:
- Limited data on China's internal reforms
- Untested nature of new frameworks
- Political factors affecting implementation

---

### 10.4 Cross-Domain Example

#### Question CROSS-001 (Hard, Analytical)

**Question**: How might advances in AI-driven drug discovery impact pharmaceutical company valuations over the next decade, and which companies are best positioned to benefit?

**Required Synthesis Across**:
- AI/ML: Current capabilities, trajectory of AI drug discovery
- Investment: Pharma company analysis, R&D productivity metrics
- General: Regulatory considerations, scientific limitations

**Expected Dimensions**:
- Technology assessment (current state, trajectory)
- Company positioning analysis
- Market size and timing estimates
- Risk factors and uncertainties

---

## Appendix A: Detailed Scoring Rubrics

### A.1 Question Decomposition Rubric

| Score Range | Completeness | Logical Structure | Granularity | Independence |
|-------------|--------------|-------------------|-------------|--------------|
| 90-100 | Covers all aspects, no gaps | Perfect hierarchy, logical flow | Optimal scope for each | Minimal redundancy, full coverage |
| 75-89 | Minor gaps | Good structure, minor issues | Mostly appropriate | Some overlap, good coverage |
| 50-74 | Notable gaps | Adequate structure | Mixed granularity | Notable redundancy |
| 25-49 | Major gaps | Poor structure | Mostly inappropriate | High redundancy or gaps |
| 0-24 | Fails to decompose | Incoherent | Wrong level entirely | Either highly redundant or missing coverage |

### A.2 Synthesis Coherence Detailed Rubric

**Score 5 - Excellent**
- Factual accuracy: No errors detected
- Organization: Clear, logical flow with appropriate sections
- Depth: Comprehensive coverage with appropriate detail
- Clarity: Could be read by target audience without confusion
- Integration: Sources synthesized, not just listed

**Score 4 - Good**
- Factual accuracy: Minor errors that don't affect conclusions
- Organization: Good flow with minor structural issues
- Depth: Good coverage, may miss some nuances
- Clarity: Clear with occasional awkward passages
- Integration: Good synthesis with some listing

**Score 3 - Adequate**
- Factual accuracy: Some errors, may affect minor conclusions
- Organization: Adequate but could be improved
- Depth: Covers main points, lacks depth
- Clarity: Understandable but requires effort
- Integration: Mix of synthesis and listing

**Score 2 - Poor**
- Factual accuracy: Significant errors affecting conclusions
- Organization: Poorly structured
- Depth: Missing important aspects
- Clarity: Difficult to follow
- Integration: Mostly listing, little synthesis

**Score 1 - Unacceptable**
- Factual accuracy: Pervasive errors
- Organization: Incoherent
- Depth: Fails to address question
- Clarity: Unintelligible
- Integration: No synthesis attempted

---

## Appendix B: API Schema

### B.1 Full OpenAPI Specification

```yaml
openapi: 3.0.0
info:
  title: ResearchBench API
  version: 1.0.0
  description: API for submitting and retrieving ResearchBench evaluations

servers:
  - url: https://api.researchbench.org/v1

paths:
  /submissions:
    post:
      summary: Submit evaluation
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Submission'
      responses:
        '202':
          description: Submission accepted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SubmissionResponse'

  /submissions/{submission_id}:
    get:
      summary: Get submission results
      parameters:
        - name: submission_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Submission results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SubmissionResults'

  /questions:
    get:
      summary: Get questions for evaluation
      parameters:
        - name: split
          in: query
          schema:
            type: string
            enum: [dev, test]
        - name: domain
          in: query
          schema:
            type: string
            enum: [aiml, investment, general]
      responses:
        '200':
          description: List of questions
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Question'

components:
  schemas:
    Submission:
      type: object
      required:
        - submission_id
        - system_name
        - system_version
        - questions
      properties:
        submission_id:
          type: string
          format: uuid
        system_name:
          type: string
        system_version:
          type: string
        timestamp:
          type: string
          format: date-time
        questions:
          type: array
          items:
            $ref: '#/components/schemas/QuestionResponse'

    QuestionResponse:
      type: object
      required:
        - question_id
        - response
      properties:
        question_id:
          type: string
        response:
          $ref: '#/components/schemas/Response'

    Response:
      type: object
      required:
        - decomposition
        - sources
        - synthesis
        - citations
        - gaps
        - counterarguments
        - confidence_statements
      properties:
        decomposition:
          $ref: '#/components/schemas/Decomposition'
        sources:
          type: array
          items:
            $ref: '#/components/schemas/Source'
        synthesis:
          $ref: '#/components/schemas/Synthesis'
        citations:
          type: array
          items:
            $ref: '#/components/schemas/Citation'
        gaps:
          type: array
          items:
            $ref: '#/components/schemas/Gap'
        counterarguments:
          type: array
          items:
            $ref: '#/components/schemas/Counterargument'
        confidence_statements:
          type: array
          items:
            $ref: '#/components/schemas/ConfidenceStatement'
        metadata:
          $ref: '#/components/schemas/Metadata'

    Decomposition:
      type: object
      properties:
        sub_questions:
          type: array
          items:
            type: object
            properties:
              id:
                type: string
              text:
                type: string
              parent_id:
                type: string
                nullable: true
              rationale:
                type: string

    Source:
      type: object
      properties:
        url:
          type: string
          format: uri
        title:
          type: string
        accessed_date:
          type: string
          format: date
        relevance_explanation:
          type: string

    Synthesis:
      type: object
      properties:
        content:
          type: string
        structure:
          type: array
          items:
            type: object
            properties:
              section:
                type: string
              content:
                type: string

    Citation:
      type: object
      properties:
        claim:
          type: string
        source_url:
          type: string
          format: uri
        quote:
          type: string
          nullable: true
        location:
          type: string

    Gap:
      type: object
      properties:
        description:
          type: string
        category:
          type: string
          enum: [data, temporal, methodological, scope, consensus]
        importance:
          type: string
          enum: [high, medium, low]

    Counterargument:
      type: object
      properties:
        position:
          type: string
        source_url:
          type: string
          format: uri
          nullable: true
        explanation:
          type: string

    ConfidenceStatement:
      type: object
      properties:
        claim:
          type: string
        confidence:
          type: number
          minimum: 0
          maximum: 1
        justification:
          type: string

    Metadata:
      type: object
      properties:
        processing_time_seconds:
          type: number
        sources_consulted:
          type: integer
        model_calls:
          type: integer

    SubmissionResponse:
      type: object
      properties:
        submission_id:
          type: string
        status:
          type: string
          enum: [accepted, processing, completed, failed]
        estimated_completion:
          type: string
          format: date-time

    SubmissionResults:
      type: object
      properties:
        submission_id:
          type: string
        status:
          type: string
        overall_score:
          type: number
        dimension_scores:
          type: object
          properties:
            question_decomposition:
              type: number
            source_coverage:
              type: number
            citation_accuracy:
              type: number
            synthesis_coherence:
              type: number
            gap_identification:
              type: number
            counterargument_discovery:
              type: number
            confidence_calibration:
              type: number
        domain_scores:
          type: object
        difficulty_scores:
          type: object
        per_question_results:
          type: array
          items:
            type: object

    Question:
      type: object
      properties:
        question_id:
          type: string
        text:
          type: string
        domain:
          type: string
        difficulty:
          type: string
        question_type:
          type: string
```

---

## References

1. Jimenez, C. E., et al. (2024). "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" *ICLR 2024*.

2. Liu, X., et al. (2023). "AgentBench: Evaluating LLMs as Agents." *arXiv:2308.03688*.

3. Thorne, J., et al. (2018). "FEVER: A Large-scale Dataset for Fact Extraction and VERification." *NAACL 2018*.

4. Yang, Z., et al. (2018). "HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering." *EMNLP 2018*.

5. Dasigi, P., et al. (2021). "A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers." *NAACL 2021*.

6. Guo, D., et al. (2024). "DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model." *arXiv*.

7. Nori, H., et al. (2023). "Can Generalist Foundation Models Outcompete Special-Purpose Tuning?" *arXiv:2311.16452*.

8. Anthropic. (2024). "The Claude Model Card and Evaluations." *Anthropic Technical Report*.

9. Guo, W., & Caliskan, A. (2021). "Detecting Emergent Intersectional Biases." *AIES 2021*.

10. Lin, S., et al. (2022). "TruthfulQA: Measuring How Models Mimic Human Falsehoods." *ACL 2022*.

---

## Citation

If you use ResearchBench in your research, please cite:

```bibtex
@inproceedings{researchbench2026,
  title={ResearchBench: A Comprehensive Benchmark for Evaluating Research Agents},
  author={[Authors]},
  booktitle={Proceedings of NeurIPS 2026 Datasets and Benchmarks Track},
  year={2026},
  note={Under review}
}
```

---

## License

ResearchBench is released under the CC BY-NC 4.0 license for research purposes. Commercial use requires separate licensing agreement.

---

## Contact

- Website: https://researchbench.org
- Email: contact@researchbench.org
- GitHub: https://github.com/researchbench/researchbench

---

*Document Version: 0.1.0*
*Last Updated: January 2026*
