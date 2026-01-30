# BAIR Grant Application

**Applicant:** Dr. Paul Jialiang Wu
**Project:** research-loop
**Date:** January 2026

---

## What We Know About BAIR Grant

### Program Overview

| Aspect | Details |
|--------|---------|
| **Funding** | Up to $250,000 uncapped SAFE |
| **Total Pool** | $12M for Berkeley AI startups |
| **Eligibility** | UC Berkeley-affiliated AI researchers (PhD, Masters, Postdoc, Faculty, Undergrads, Affiliates) |
| **Requirements** | No incorporated company needed |
| **Application** | Rolling basis, apply anytime |
| **Focus** | Support prior to starting up |

### Who Can Apply
- PhD and Masters students
- Postdoctoral fellows
- Faculty
- Undergraduates
- **Affiliates** ← This is the path for non-Berkeley researchers

### Key Partners
- The House Fund (VC backing)
- BAIR Professors: Ion Stoica, Joey Gonzalez, Ken Goldberg, Kurt Keutzer, Trevor Darrell
- AI-first corporations
- Philanthropists

---

## ELIGIBILITY STRATEGY

### The Challenge
BAIR Grant is primarily for Berkeley-affiliated researchers. Dr. Wu is Yale postdoc, not Berkeley.

### Potential Paths to Eligibility

**Option 1: Berkeley Affiliate Status**
- Apply to become a BAIR Visiting Researcher or Industry Affiliate
- Some programs allow industry professionals to affiliate
- Contact BAIR directly about affiliate researcher programs

**Option 2: Berkeley Collaboration**
- Find a Berkeley PhD student or postdoc interested in research agents
- They apply as primary, you're a co-founder/collaborator
- ResearchBench could be attractive to Berkeley NLP/ML researchers

**Option 3: "Open to All" Interpretation**
- The grant states: "While this program focuses on those conducting research under the BAIR umbrella, they also welcome all UC Berkeley-affiliated AI researchers"
- Also: "While the grant is targeted towards BAIR Lab's research community, the grant is open to all prospective entrepreneurs on campus"
- Worth applying and explaining the connection

**Option 4: Berkeley Extension/Alumni Connection**
- If you have any Berkeley connection (courses, collaborations, alumni network)
- Highlight it in application

---

## APPLICATION (Assuming Eligibility Path Found)

### Basic Information

**Name:** Dr. Paul Jialiang Wu

**Email:** wjlgatech@gmail.com

**Berkeley Affiliation:** [To be established - see eligibility strategy]

**Current Position:** LLM Architect Manager, Accenture

**Background:**
- Yale Postdoc, Computational Immunology
- Principal Data Scientist, Genentech
- LLM Architect Manager, Accenture

---

### Research/Project Description

**Project Title:** research-loop: Multi-Agent Research Synthesis with Benchmark Evaluation

**One-line summary:**
Open-source multi-agent system that automates research synthesis, with ResearchBench—the first comprehensive benchmark for evaluating AI research agents.

**Problem Statement:**

Researchers spend 40-60% of their time on literature review and synthesis. This represents a massive productivity drain across academia and industry. Current tools help find papers but don't help understand or synthesize them. LLMs hallucinate and lack citations.

This problem is particularly acute at research institutions like Berkeley, where PhD students and postdocs spend years on literature synthesis that could be dramatically accelerated.

**Technical Approach:**

research-loop uses a multi-agent architecture:

1. **Query Decomposition Agent** - Breaks complex research questions into searchable sub-queries
2. **Multi-Source Search Agent** - Queries arXiv, PubMed, Semantic Scholar, Exa.ai
3. **Evidence Evaluation Agent** - Assesses source quality, relevance, recency
4. **Synthesis Agent** - Generates cited summaries with confidence scores

Key innovation: **Contextual Experience Replay (CER)**
- Stores successful research patterns with rich context
- Retrieves relevant experiences for new queries
- Achieves 51% improvement in research quality (A/B tested)

**ResearchBench Contribution:**

We've created the first comprehensive benchmark for research agents:
- 500 curated questions across 5 domains
- Ground truth for evaluation
- Metrics: decomposition quality, source coverage, synthesis accuracy
- Open-source release planned

This addresses a critical gap: there's no standard way to evaluate research agent capabilities. ResearchBench enables systematic comparison and improvement.

**Relevance to BAIR/Berkeley:**

1. **BAIR researchers are the target users** - PhD students and postdocs doing literature review
2. **Builds on Berkeley research** - Leverages techniques from Berkeley NLP, ML communities
3. **Open-source ethos** - Aligned with Berkeley's commitment to open AI research
4. **Benchmark contribution** - ResearchBench could become a standard evaluation tool

---

### Technical Validation

**What have you built?**

| Component | Status | Tests |
|-----------|--------|-------|
| Core multi-agent system | ✅ Complete | 465+ passing |
| Exa.ai integration | ✅ Complete | 39 tests |
| Semantic Scholar integration | ✅ Complete | 45 tests |
| ResearchBench dataset | ✅ Complete | 500 questions |
| Contextual Experience Replay | ✅ Complete | 51% improvement |
| Human checkpoint system | ✅ Complete | High-stakes domains |
| Medical Research Adapter | 🔄 In progress | - |

**Measurable Results:**

- **51% improvement** in research quality via CER (blind A/B testing)
- **465+ tests** passing (production-quality code)
- **500 benchmark questions** across 5 domains

---

### Funding Use

**How will you use the $250K?**

| Use | Amount | Timeline |
|-----|--------|----------|
| Full-time founder salary (12 months) | $150K | Months 1-12 |
| Cloud compute (training, inference) | $50K | Ongoing |
| User research & pilots | $25K | Months 3-9 |
| Legal/incorporation | $10K | Month 1 |
| Marketing/community | $15K | Months 6-12 |

**Milestones:**

- **Month 3:** Public launch, 100 beta users
- **Month 6:** ResearchBench on Hugging Face, 1000 users
- **Month 9:** First enterprise pilot
- **Month 12:** Seed fundraise or revenue

---

### Why BAIR Grant?

**Why this program specifically?**

1. **Research-first culture** - BAIR understands that research tools need research rigor
2. **Pre-startup support** - I need to transition from employment to founder; BAIR supports this
3. **Berkeley AI network** - Access to researchers who are both builders and users
4. **Mentorship** - BAIR professors (Stoica, Gonzalez, Goldberg) have commercialized research

**What do you need beyond funding?**

1. **Berkeley researcher pilots** - PhD students to test research-loop on real projects
2. **Technical feedback** - Is our approach (CER, multi-agent) sound?
3. **Benchmark validation** - Would BAIR researchers use ResearchBench?
4. **Introductions** - To other research institutions, enterprise R&D teams

---

### Team

**Solo Founder:** Dr. Paul Jialiang Wu

| Experience | Relevance |
|------------|-----------|
| Yale Postdoc (Computational Immunology) | Understands research workflows, academic culture |
| Genentech (Principal Data Scientist) | Built ML for drug discovery, knows biotech R&D |
| Accenture (LLM Architect Manager) | Enterprise AI deployment, large-scale systems |

**Seeking:**
- Technical co-founder (ML/NLP background)
- Berkeley collaborator for research validation

---

### Additional Materials

**Links:**
- GitHub: github.com/wjlgatech/claude-loop
- ResearchBench spec: [docs link]
- Demo video: [pending]

**Publications/Background:**
- [List relevant publications from Yale postdoc]
- [Any relevant patents or papers]

---

## ALTERNATIVE: Berkeley Collaboration Email

If direct application isn't possible, here's an email to find a Berkeley collaborator:

```
Subject: Collaboration Opportunity: ResearchBench + BAIR Grant

Hi [Berkeley Researcher],

I'm Dr. Paul Jialiang Wu (Yale postdoc → Genentech → Accenture). I've built
research-loop, a multi-agent research synthesis system with ResearchBench—
the first comprehensive benchmark for AI research agents.

I'm looking for a Berkeley collaborator to:
1. Apply to BAIR Grant together ($250K uncapped SAFE)
2. Validate ResearchBench with Berkeley PhD students
3. Potentially co-author a paper on research agent evaluation

What you'd get:
- Co-founder equity in research-loop
- Working tool (465+ tests passing, 51% improvement measured)
- First-author on ResearchBench paper

What I bring:
- Complete prototype + benchmark
- Enterprise AI experience (Genentech, Accenture)
- Full-time commitment upon funding

Would you have 15 minutes to chat?

Best,
Dr. Paul Jialiang Wu
```

**Target researchers:**
- Berkeley NLP PhD students working on agents
- BAIR postdocs in ML/information retrieval
- Anyone publishing on research automation

---

## Summary: Path Forward

| Option | Probability | Action |
|--------|-------------|--------|
| Direct BAIR application | Medium | Apply, explain relevance to Berkeley community |
| Berkeley collaboration | High | Email 5-10 BAIR researchers with collaboration offer |
| Berkeley affiliate status | Low | Inquire about visiting researcher programs |
| Alternative: AI2 Incubator | High | Apply in parallel (no Berkeley requirement) |

**Recommendation:** Apply to BAIR Grant directly while simultaneously reaching out to Berkeley researchers for collaboration. Apply to AI2 Incubator in parallel as it has no affiliation requirements.

---

*Application prepared: January 2026*
*Status: Ready to submit, pending eligibility confirmation*
