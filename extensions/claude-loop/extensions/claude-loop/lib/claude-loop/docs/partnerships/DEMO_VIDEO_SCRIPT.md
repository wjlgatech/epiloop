# Stanford AIMI Demo Video Script

## research-loop: AI-Powered Research Orchestration for Health AI

**Duration:** 3 minutes (180 seconds)
**Target Audience:** Stanford AIMI faculty, researchers, program committee
**Tone:** Professional, evidence-driven, accessible to both technical and non-technical audiences

---

## Scene Breakdown

### OPENING (0:00 - 0:15) | 15 seconds

**[SCENE: Dark screen fades to research-loop logo with subtle neural network animation]**

**VOICEOVER:**
> "What if you could have a team of AI research assistants that learn from every query they process... and get smarter with every investigation?"

**[SCENE: Quick montage - researcher overwhelmed by papers, split to organized research dashboard]**

**VOICEOVER:**
> "Introducing research-loop - autonomous research orchestration for the AI era."

**ON SCREEN:**
- research-loop logo
- Tagline: "From question to insight - autonomously"
- Stanford AIMI partner badge (proposed)

**VISUAL NOTES:**
- Clean, medical/academic aesthetic (white, blue, subtle green accents)
- Brief particle animation suggesting connected knowledge
- Fade transition to next section

---

### PROBLEM STATEMENT (0:15 - 0:35) | 20 seconds

**[SCENE: Split screen - researcher at desk surrounded by papers / timeline showing hours passing]**

**VOICEOVER:**
> "Today's researchers face an impossible challenge. Medical literature doubles every 73 days. AI papers hit arXiv faster than anyone can read them."

**[SCENE: Data visualization - exponentially growing publication graph]**

**VOICEOVER:**
> "Studies show researchers spend over 40% of their time just on literature review. Information is scattered across arXiv, PubMed, clinical trials, and FDA databases. Synthesis is manual, time-consuming, and error-prone."

**ON SCREEN (animated statistics):**
- "40%+ of research time on literature review"
- "2.5M+ new papers published annually"
- "Information silos: arXiv | PubMed | ClinicalTrials.gov | FDA"
- "Manual synthesis: slow, inconsistent, incomplete"

**VISUAL NOTES:**
- Frustrated researcher visual (relatable, not dramatic)
- Growing stack of papers animation
- Red highlights on "manual" and "error-prone"
- Smooth transition to solution

---

### DEMO: AI-ML RESEARCH QUERY (0:35 - 1:35) | 60 seconds

**[SCENE: Clean terminal/dashboard interface - research-loop starting]**

**VOICEOVER:**
> "Let's see research-loop in action. We'll ask a complex question about vision transformers for medical imaging."

**[SCENE: Terminal shows command being typed]**

**ON SCREEN (Terminal):**
```
$ ./research-loop.sh --adapter ai-ml \
    "What are the latest advances in vision transformers for medical image classification?"
```

---

#### Sub-scene 1: Question Decomposition (0:45 - 0:55) | 10 seconds

**[SCENE: Animated diagram - main question splits into 4-5 sub-questions]**

**VOICEOVER:**
> "First, the Question Decomposer breaks this into targeted sub-questions - each designed to capture a different dimension of the answer."

**ON SCREEN (Animated):**
```
Main Question
    |
    +-- "What architectural innovations define recent ViT variants?"
    +-- "How do these compare to CNNs on medical imaging benchmarks?"
    +-- "What are the computational requirements and trade-offs?"
    +-- "Which approaches show promise for radiology applications?"
```

**VISUAL NOTES:**
- Tree diagram animation, branches growing outward
- Each sub-question appears with a subtle "pop" animation

---

#### Sub-scene 2: Parallel Agent Execution (0:55 - 1:10) | 15 seconds

**[SCENE: Split view showing multiple agents working simultaneously]**

**VOICEOVER:**
> "Now, specialized agents work in parallel. The Academic Scanner searches arXiv and Semantic Scholar. The Technical Diver examines GitHub repositories and documentation. The Benchmark Analyst tracks state-of-the-art results."

**ON SCREEN (Split panels, each with activity indicators):**

| Agent | Activity | Sources |
|-------|----------|---------|
| Academic Scanner | Searching cs.CV, cs.AI categories... | arXiv, Semantic Scholar |
| Technical Diver | Analyzing implementations... | GitHub, Papers with Code |
| Benchmark Analyst | Checking SOTA on ImageNet, MIMIC-CXR... | Papers with Code |

**VISUAL NOTES:**
- Animated search icons, progress bars
- Source logos appearing as agents find relevant papers
- Citations counter incrementing (8... 12... 15...)

---

#### Sub-scene 3: Synthesis with Confidence Scores (1:10 - 1:25) | 15 seconds

**[SCENE: Research Synthesizer combining findings into structured output]**

**VOICEOVER:**
> "The Research Synthesizer combines all findings, calculates confidence scores, and identifies where sources agree - or disagree."

**ON SCREEN (Synthesis dashboard):**
```
+------------------------------------------+
|         SYNTHESIS COMPLETE               |
+------------------------------------------+
| Confidence Score: 78/100                 |
| Sources: 15 papers, 4 GitHub repos       |
| Agent Agreement: High (3/3 agents)       |
|                                          |
| Key Findings:                            |
| 1. Hierarchical ViTs outperform flat...  |
| 2. Pre-training on natural images...     |
| 3. Computational cost remains barrier... |
+------------------------------------------+
```

**VISUAL NOTES:**
- Confidence score gauge animation (filling to 78%)
- Green checkmarks appearing next to verified findings
- Source count incrementing

---

#### Sub-scene 4: Gap Identification & Counterarguments (1:25 - 1:35) | 10 seconds

**[SCENE: Quality control section with gaps and counterarguments highlighted]**

**VOICEOVER:**
> "research-loop doesn't just find what's known - it identifies gaps and presents counterarguments, ensuring balanced research synthesis."

**ON SCREEN (Quality panel):**
```
GAPS IDENTIFIED (2):
  - Limited data on long-tail medical conditions
  - Few studies on deployment in resource-limited settings

COUNTERARGUMENTS:
  - "Traditional CNNs may still outperform on small datasets"
    Source: Nature MI 2024

FACT-CHECK STATUS: 14/15 claims verified
```

**VISUAL NOTES:**
- Yellow warning icons for gaps
- Red/orange highlight for counterarguments
- Green checkmark for fact-checked claims

---

### KEY DIFFERENTIATORS (1:35 - 2:20) | 45 seconds

**[SCENE: Clean infographic slides, one per differentiator]**

#### Differentiator 1: ResearchBench (1:35 - 1:47) | 12 seconds

**[SCENE: ResearchBench logo and statistics]**

**VOICEOVER:**
> "ResearchBench is the first comprehensive benchmark for evaluating research agents. 500 expert-curated questions across 5 domains, with ground truth for rigorous evaluation."

**ON SCREEN:**
```
+------------------------------------------+
|           RESEARCHBENCH                  |
|    First Comprehensive Research Benchmark |
+------------------------------------------+
|                                          |
|   500 QUESTIONS | 5 DOMAINS | 100 GT     |
|                                          |
|   Domains:                               |
|   - AI-ML (100 questions)                |
|   - Scientific Research (100)            |
|   - Technical Analysis (100)             |
|   - Investment Research (100)            |
|   - Interdisciplinary (100)              |
|                                          |
|   Difficulty: Easy | Medium | Hard       |
+------------------------------------------+
```

**VISUAL NOTES:**
- Animated counter showing "500" questions
- Domain icons: brain (AI-ML), flask (Scientific), gear (Technical), chart (Investment), puzzle (Interdisciplinary)
- "Ground Truth" badge highlighted

---

#### Differentiator 2: Meta-Learning with CER (1:47 - 1:59) | 12 seconds

**[SCENE: Before/after comparison showing improvement]**

**VOICEOVER:**
> "Contextual Experience Replay enables research-loop to learn from every query. In our evaluations, this meta-learning approach delivered a 51% improvement in research quality."

**ON SCREEN:**
```
CONTEXTUAL EXPERIENCE REPLAY (CER)
"Learning from every investigation"

+----------------+     +----------------+
|   BASELINE     |     |   WITH CER     |
|                |     |                |
|   Score: 52    | --> |   Score: 78    |
|                |     |                |
+----------------+     +----------------+

         +51% IMPROVEMENT

How it works:
  1. Store successful patterns
  2. Retrieve relevant experience
  3. Apply learned strategies
  4. Improve over time
```

**VISUAL NOTES:**
- Animated arrow showing improvement
- Circular diagram: Query -> Learn -> Apply -> Improve
- "+51%" in large, bold green text

---

#### Differentiator 3: Quality Gates (1:59 - 2:09) | 10 seconds

**[SCENE: Quality gate pipeline visualization]**

**VOICEOVER:**
> "Every finding passes through quality gates: fact-checking against primary sources, source verification, and confidence calibration - critical for high-stakes domains like medicine."

**ON SCREEN:**
```
QUALITY GATES PIPELINE

[Finding] --> [Fact Checker] --> [Source Verifier] --> [Confidence Scorer]
                  |                    |                      |
                  v                    v                      v
            "Claim verified"    "Source credible"     "78/100 confidence"

GATES PASSED: 14/15  |  VERIFICATION RATE: 93%
```

**VISUAL NOTES:**
- Pipeline animation with checkmarks appearing
- One finding showing yellow "needs review" status
- Overall green "quality approved" badge

---

#### Differentiator 4: Human Checkpoints (2:09 - 2:20) | 11 seconds

**[SCENE: Human-in-the-loop checkpoint interface]**

**VOICEOVER:**
> "For high-stakes research, human checkpoints ensure expert oversight. Low-confidence findings trigger mandatory review - no automation without verification."

**ON SCREEN:**
```
+------------------------------------------+
|     HUMAN CHECKPOINT REQUIRED            |
+------------------------------------------+
|                                          |
|  Finding: "Novel drug interaction..."    |
|  Confidence: 45/100 (Below threshold)    |
|  Trigger: High-stakes medical domain     |
|                                          |
|  Options:                                |
|  [APPROVE]  [REQUEST MORE DEPTH]         |
|  [REDIRECT] [CANCEL]                     |
|                                          |
+------------------------------------------+

CHECKPOINT TRIGGERS:
  - Medical/Legal domains (always)
  - Confidence < 50%
  - Conflicting findings
```

**VISUAL NOTES:**
- Pulsing alert indicator
- Human icon prominently displayed
- "Safety first" messaging subtle but present

---

### MEDICAL RESEARCH VISION (2:20 - 2:50) | 30 seconds

**[SCENE: Future roadmap with medical adapter concept]**

**VOICEOVER:**
> "Our vision for health AI research: a Medical Research Adapter purpose-built for AIMI's mission."

**[SCENE: Animated diagram showing medical data sources connecting to research-loop]**

**VOICEOVER:**
> "Integrating PubMed, ClinicalTrials.gov, and FDA databases. Automating systematic reviews. Synthesizing clinical evidence with verified citations."

**ON SCREEN:**
```
MEDICAL RESEARCH ADAPTER (Proposed)
"Accelerating Health AI Research"

Data Sources:               Capabilities:
+----------------+          +------------------------+
| PubMed         |          | Systematic Review      |
| ClinicalTrials |    -->   | Automation             |
| FDA CDRH       |          |                        |
| bioRxiv        |          | Clinical Evidence      |
| MIMIC          |          | Synthesis              |
+----------------+          |                        |
                            | Regulatory Pathway     |
                            | Research               |
                            +------------------------+

Specialized Agents:
  - Clinical Evidence Reviewer
  - Regulatory Tracker
  - Safety Signal Monitor
  - Trial Design Analyst
```

**VOICEOVER:**
> "This directly aligns with AIMI's mission: advancing health through AI innovation, accelerating discovery, and ensuring AI safety in clinical applications."

**VISUAL NOTES:**
- Stanford AIMI and research-loop logos side by side
- Medical imagery (subtle): DNA helix, medical imaging icons
- "Alignment" visual connecting AIMI mission to research-loop capabilities

---

### CALL TO ACTION (2:50 - 3:00) | 10 seconds

**[SCENE: Clean closing slide with contact information]**

**VOICEOVER:**
> "research-loop: ready to accelerate health AI research. Let's build the future of medical discovery together."

**ON SCREEN:**
```
+------------------------------------------+
|                                          |
|           PARTNERSHIP OPPORTUNITY        |
|                                          |
|   research-loop + Stanford AIMI          |
|                                          |
|   "Accelerating Health AI Research"      |
|                                          |
|   Contact: Wu, Founder                   |
|   Email: wjlgatech@gmail.com             |
|   GitHub: github.com/wjlgatech/claude-loop|
|                                          |
|   Ready for:                             |
|   - Live Demo                            |
|   - Technical Deep-Dive                  |
|   - Collaboration Discussion             |
|                                          |
+------------------------------------------+
```

**VISUAL NOTES:**
- Fade to research-loop + AIMI logos
- Contact information clearly visible
- Subtle call-to-action button animation
- End with clean fade to black

---

## Production Notes

### Visual Style Guide
- **Color Palette:** Dark navy (#1a1a2e), Medical blue (#4a90d9), Success green (#28a745), Alert amber (#ffc107)
- **Typography:** Clean sans-serif (Inter, SF Pro, or Roboto)
- **Animation:** Subtle, professional - no flashy transitions
- **Icons:** Minimal line-art style, consistent stroke weight

### Audio
- **Music:** Subtle, inspiring background track (royalty-free, tech/innovation genre)
- **Voice:** Professional voiceover artist, measured pace, confident but not aggressive
- **Sound Effects:** Minimal - soft "confirmation" sounds for checkmarks, subtle typing sounds

### Screen Recordings
- **Terminal:** Use clean, dark theme with good contrast
- **Dashboard:** research-loop dashboard if available, or high-fidelity mockup
- **Resolution:** 1920x1080 minimum, 4K preferred

### B-Roll Suggestions
- Researcher working at computer (stock footage)
- Medical imaging examples (with appropriate permissions)
- Stanford campus/AIMI building exterior (if permitted)
- Abstract data visualization animations

### Accessibility
- Include closed captions for all voiceover
- Ensure sufficient color contrast for text
- Audio descriptions available for key visuals

---

## Script Timing Summary

| Section | Duration | Running Time |
|---------|----------|--------------|
| Opening | 15s | 0:00 - 0:15 |
| Problem Statement | 20s | 0:15 - 0:35 |
| Demo: Question Decomposition | 10s | 0:35 - 0:45 |
| Demo: Parallel Agent Execution | 15s | 0:45 - 1:10 |
| Demo: Synthesis with Confidence | 15s | 1:10 - 1:25 |
| Demo: Gaps & Counterarguments | 10s | 1:25 - 1:35 |
| Differentiator: ResearchBench | 12s | 1:35 - 1:47 |
| Differentiator: CER Meta-Learning | 12s | 1:47 - 1:59 |
| Differentiator: Quality Gates | 10s | 1:59 - 2:09 |
| Differentiator: Human Checkpoints | 11s | 2:09 - 2:20 |
| Medical Research Vision | 30s | 2:20 - 2:50 |
| Call to Action | 10s | 2:50 - 3:00 |
| **TOTAL** | **180s** | **3:00** |

---

## Key Messages to Emphasize

1. **For Technical Audience:**
   - ResearchBench: First rigorous benchmark (500 questions, 5 domains)
   - CER: 51% measurable improvement via meta-learning
   - Multi-agent architecture with specialized roles
   - Quality gates prevent hallucination propagation

2. **For Non-Technical Audience:**
   - Researchers get more time for creative work
   - AI handles literature review systematically
   - Human oversight ensures safety and accuracy
   - Directly aligned with AIMI's health AI mission

3. **Partnership Value:**
   - Mutual benefit: AIMI gets research acceleration, research-loop gets domain expertise
   - Open source commitment
   - Ready for immediate collaboration

---

*Script prepared: January 18, 2026*
*Version: 1.0*
*Duration: 3 minutes*
